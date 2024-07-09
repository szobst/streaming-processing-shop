import json
import multiprocessing
import threading
from time import sleep
from typing import List, Optional
from multiprocessing import Queue,Lock,Manager, Value,Event
import typing
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import logging
import sys
from loguru import logger


##########################
##    Model danych
##########################


class Product(): 
    def __init__(self:int,stock:int,price:int,manager:Manager):
        self.price = manager.Value('i',price)
        self.stock = manager.Value('i',stock)

        self.sold = manager.Value('i',0)

        self.reserved = manager.Value('i',0)

        self.counter = manager.Value('i',0)
    
        self.lock = manager.Lock()
    # pojedyncz zamowienie 
    def singleOrder(self,amount:int):
        with self.lock:
            if(self.stock.value>= amount):
                self.stock.value = self.stock.value - amount
                self.sold.value = self.sold.value + amount
                return True
            else:
                return False
    # pojedyncza rezerwacja
    def singleReservation(self,amount:int):
        with self.lock:
            if(self.stock.value>= amount):
                self.stock.value = self.stock.value - amount
                self.reserved.value = self.reserved.value + amount
                #self.sold.value = self.sold.value + amount
                return True
            else:
                return False
    # odbior rezerwacji
    def singleCollection(self,amount:int):
        with self.lock:
            if(self.reserved.value>= amount):
                self.reserved.value = self.reserved.value - amount
                #self.sold.value = self.sold.value + amount
                return True
            else:
                return False
    # zwraca cena. co 10 = 0
    # pojedyncze zaopatrzenie
    # Zwraca liczne produktow po dostawie

    def getPrice(self,promo):
            if(promo):
                return 0
            else:
                return self.price.value

    def singleSuplly(self,amount: int):
        with self.lock:
            self.stock.value = self.stock.value + amount
            return self.stock.value
    
    # zwraca blokade
    def getLock(self):
        return self.lock
    
    # Funkcje uzywane podczas tworzenia roportow
    # Używanie tylko przez funkcje z klasy Warehouse!!
    # Nie posiadaja blokad

    def getPriceRap(self):
        return self.price.value
    def getSoldRap(self):
        return self.sold.value
    def getStockRap(self):
        return self.stock.value

class Warehouse():
    def __init__(self,stock,price,products,manager):
        
        self.names = products
        self.products = manager.dict()
        self.counter = manager.Value("i",0)
        self.wareLock = manager.Event()
        self.wareLock.set()
        self.cenaLock = manager.Lock()

        for name in products:
            product = Product(stock=stock,price=price,manager=manager)
            self.products[name] = product
    
    def getCounter(self):
        self.counter.value = self.counter.value + 1
        if (self.counter.value==10):
    
            self.counter.value = 0
            return True
        else:
            return False
        
    def get(self, name:str):
        return self.products.get(name)
    
    def getRaport(self):

        raport = dict()

        for name in self.names:
            product = self.get(name)
            raport[name] = product.getSoldRap()

        return raport
    
    def getPrices(self):
        
        raport = dict()
        
        for name in self.names:
            product = self.get(name)
            raport[name] = product.getPriceRap()

        return raport
    def getStocks(self):

        raport = dict()
        
        for name in self.names:
            product = self.get(name)
            raport[name] = product.getStockRap()

        return raport
    
    def waitForAll(self):
        
        for name in self.names:
            product = self.products[name]
            product.getLock().acquire()
            product.getLock().release()

    def blockPriceCheck(self):
        return self.cenaLock

    # Zablokuj wszystkie operacje
    def lockAll(self):
        self.wareLock.clear()

    # Odblokuj wszyskie operacje
    def releaseAll(self):
        self.wareLock.set()
    def getEvent(self):
        return self.wareLock
class Actions(BaseModel):
    id: Optional[int] = None
    typ: Optional[str] = None
    product: Optional[str] = None
    liczba: Optional[int] = None
    grupaProduktów: Optional[typing.Dict[str, int]] = None
    cena: Optional[int] = None

class Replies(BaseModel):
    id: Optional[int] = None
    typ: Optional[str] = None
    product: Optional[str] = None
    liczba: Optional[int] = None
    cena: Optional[int] = None
    grupaProduktów: Optional[typing.Dict[str, int]] = None
    stanMagazynów: Optional[typing.Dict[str, int]] = None
    raportSprzedaży: Optional[typing.Dict[str, int]] = None
    cenaZmieniona : Optional[bool] = None
    zrealizowanePrzywrócenie : Optional[bool] = None
    zrealizowaneZamowienie : Optional[bool] = None
    zrealizowaneWycofanie : Optional[bool] = None
    zebraneZaopatrzenie : Optional[bool] = None
    studentId: Optional[int] = None
    timestamp: Optional[int] = None

class Handshake(BaseModel):
    ip_addr: str
    port: int
    indeks : int