# Aplikacja kliencka

Aplikacja do odbierania listy akcji i odsyłania odpowiedzi do serwera.

Kroki: 

* Klient laczy sie z serwerem podajac swoj adres ip, port oraz nr indeksu
* Serwer zbiera polaczenia i generuje dane
* Klient odbiera dane i odsyła wynik
* Serwer waliduje wynik podaje w terminalu, czy jest w porządku.

## Funkcjonalności

- `/hello` endpoint do rejestracji na serwerze

- `/push-data` endpoint do odbioru danych

### Jak uruchomić

- in /app/main.py ustaw poprawnie wartości :

```
   SERVER_IP = 'localhost'
   SERVER_PORT = 8080

   CLIENT_IP = 'localhost'
   CLIENT_PORT = 8888
```
Zainstaluj wszystkie potrzebne pakiety i uruchom serwer lokalnie:

```
pip install -r requirements.txt

uvicorn main:app --port 8888
```


