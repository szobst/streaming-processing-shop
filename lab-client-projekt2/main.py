import json
import multiprocessing
import threading
from time import sleep
from typing import List, Optional
from multiprocessing import Queue,Lock,Manager, Value
import typing
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import logging
import sys
from loguru import logger

from classes import Warehouse,Product,Actions,Replies,Handshake

##########
### Logger
########## 

logger.add("debug.log", rotation="10 MB")
log_format = "<green>{time:YYYY-MM-DD HH:mm:ss:SSS}</green> | <level>{level: <8}</level> | <cyan>{process}</cyan> | <level>{message}</level>"
logger.configure(handlers=[{"sink": sys.stdout, "format": log_format}])


## Uruchomienie clienta
app = FastAPI()

## Ustawienie adresów i portów serwera i klienta

SERVER_IP = 'localhost'
SERVER_PORT = 8080

CLIENT_IP = 'localhost'
CLIENT_PORT = 8889

INDEKS = 478993

## Funkcja do przetwarzania danych, otrzymuje na wejściu kolejkę akcji do wykonania
def function(queue: Queue):
    
    initial_price = 5
    initial_stock = 100
    products = ["BULKA", "CHLEB", "SER", "MASLO", "MIESO", "SOK", "MAKA", "JAJKA"]
    manager = Manager()
    warehouse = Warehouse(stock=initial_stock,price=initial_price,products=products,manager=manager)


    priceLock = manager.Lock()
    n_workers = 3

    replies_list = manager.list()
    listLock = manager.Lock()
    queueLock = manager.Lock()
    logger.debug("Creating workers...")
    n_workers = 8

    workers = [multiprocessing.Process(target=process, args=(queue,warehouse,replies_list,listLock,priceLock,queueLock))
               for i in range(n_workers)]
    
    logger.debug("Workers created...")

    logger.debug("Starting procesing...")
    for worker in workers:
        worker.start()
    #Czekanie na zakonczenie procesow
    for worker in workers:
        worker.join()

    last_reply = replies_list[-1]

    prices = warehouse.getPrices()
    stocks = warehouse.getStocks()
    last_reply.grupaProduktów = prices
    last_reply.stanMagazynów = stocks
    
    replies_list[-1] = last_reply

    logger.debug("zamykamy: ceny{} , stan : {}", prices, stocks)

    logger.debug("Processes finished...")

    # Lista odpowiedzi
    wynik = list(replies_list)
    wynik = [obj.__dict__ for obj in wynik]
    
    logger.debug("Wynik: {}", last_reply)

    # Odesłanie listy wyników do serwera
    url = f"http://{SERVER_IP}:{SERVER_PORT}/action/replies"
    data = json.dumps(wynik)
    headers = {"Content-type": "application/json"}
    sleep(1)
    r = requests.post(url, data=data, headers=headers)
    logger.info(r)
    r.close()

## Metoda opisujaca process workera
def process(queue: Queue,warehouse:Warehouse,repliesList,listLock,priceLock,queueLock):
    
    # Obsługiwane operacje
    obs = {"PODAJ_CENE","REZERWACJA","ODBIÓR_REZERWACJI","POJEDYNCZE_ZAOPATRZENIE","RAPORT_SPRZEDAŻY",'ZAMKNIJ_SKLEP',"POJEDYNCZE_ZAMOWIENIE"}
    logger.debug("Worker start work")
    

    # Pracownik pracuje do poki kolejka jest nie pusta
    while not queue.empty():
        # Pobranie zapytania z kolejki
        
        with queueLock:
            if(queue.empty()):
                break
            warehouse.getEvent().wait()
            action = queue.get()
            
            if(action.typ in {"RAPORT_SPRZEDAŻY"}):   
                warehouse.getEvent().clear()

            if(action.typ in {"PODAJ_CENE"}):  
                priceLock.acquire()

        logger.debug("Rozpoczecie ({}.{}: {})",action.id, action.product, action.typ) 
        if(action.typ in obs):     
            # Tworzenie odpowiedzi
            reply = Replies()
            reply.id = action.id
            reply.typ = action.typ
            reply.studentId = INDEKS    

            # Obsługiwanie zapytan specjalnych (działajacych na wszystkich produktach)      
            if(action.typ in {"RAPORT_SPRZEDAŻY",'ZAMKNIJ_SKLEP'}):   
                #warehouse.getEvent().clear()
                match action.typ:
                    case "RAPORT_SPRZEDAŻY":
                        warehouse.waitForAll()
                        raport = warehouse.getRaport()
                        reply.raportSprzedaży = raport
                        logger.debug("{} raport: {}", raport,action.id) 
                        warehouse.getEvent().set()
                    case 'ZAMKNIJ_SKLEP':
                        # Wartosci zostana dodane w zewnetrznej funcki po zakonczeniu procesów
                        warehouse.waitForAll()
                        logger.debug("zamykamy")  
                        #warehouse.waitForAll()
            else:

                #Operacje na pojedynczych produktach (nie wymagaja blokowania calego sklepu)
                reply.product = action.product
                product = warehouse.get(action.product)
                match action.typ:
                    case "PODAJ_CENE":
                        #with warehouse.blockPriceCheck():
                            promo = warehouse.getCounter()                     
                            cena = product.getPrice(promo)
                            reply.cena = cena 
                            reply.product = action.product                   
                            logger.debug("Akcja podaj cene ({}.{}: {})",action.id, action.product, cena) 
                            priceLock.release()
                    case "REZERWACJA":
                        reply.liczba = action.liczba
                        if(product.singleReservation(action.liczba)):
                            reply.zrealizowaneZamowienie = True
                        else:
                            reply.zrealizowaneZamowienie = False
                        logger.debug("Akcja rezerwacja ({}.{}: {})",action.id, action.product, action.liczba) 

                    case "ODBIÓR_REZERWACJI":
                        if(product.singleCollection(action.liczba)):
                            reply.zrealizowaneZamowienie =True
                        else:
                            reply.zrealizowaneZamowienie = False
                        
                        logger.debug("Akcja odbior ({}.{}: {})",action.id, action.product, action.liczba) 
                    case "POJEDYNCZE_ZAOPATRZENIE":
                        reply.liczba = product.singleSuplly(action.liczba)
                        reply.zebraneZaopatrzenie = True
                        logger.debug("Akcja dostawa ({}.{}: {})",action.id, action.product, product.stock) 
                        
                    case "POJEDYNCZE_ZAMOWIENIE":
                        if(product.singleOrder(action.liczba)):
                            reply.liczba = 1
                            reply.zrealizowaneZamowienie = True
                        else:
                            reply.zrealizowaneZamowienie = False
                        logger.debug("Akcja Zamowienie ({}.{}: {})",action.id, action.product, product.stock)              
            
            with listLock:
                repliesList.append(reply)
        # Zniesienie blokady   
        else:
            logger.debug("{} Nie obslugiwane", action.typ)
    logger.debug("Worker done work")

## Odbiera listę operacji od serwera
@app.post("/push-data", status_code=201)
async def create_sensor_data(actions: List[Actions]):
    queue = Queue()
    [queue.put(i) for i in actions]
    logging.info('Processing')
    res = threading.Thread(target=function, args=(queue,))
    res.start()
    res.join()

## Laczy się z serwerem i przesyła mu swój numer IP i port
@app.get("/hello")
async def say_hello():
    url = f"http://{SERVER_IP}:{SERVER_PORT}/action/handshake"
    medata = {
        "port" : CLIENT_PORT,
        "ip_addr": CLIENT_IP,
        "indeks" : INDEKS
    }
    me = Handshake(**medata)
    data = json.dumps(medata)
    headers = {'Content-type': 'application/json'}
    res = requests.post(url, data=data, headers=headers)
    if (res.status_code == 201 or res.status_code == 200):
        return("Success")
    else:
        return(f"Error occurred {res.text}")
