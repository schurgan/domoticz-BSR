import sys
from datetime import datetime
try:
    import Domoticz
except ImportError:
    class DomoticzFake:
        def Log(self, msg): print(msg)
        def Debug(self, msg): print(msg)
        def Error(self, msg): print(msg)
    Domoticz = DomoticzFake()

try:
    import requests
except Exception as e:
    Domoticz.Error(f"Fehler beim Import von requests: {e}")
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception as e:
    Domoticz.Error(f"Fehler beim Import von BeautifulSoup: {e}")
    BeautifulSoup = None

# Hilfsklasse für WasteData
class WasteData:
    def __init__(self):
        self.entries = []

    def isComplete(self):
        return True if self.entries else False

    def getDate(self):
        if self.entries:
            return self.entries[-1].get("serviceDate_actual", "N/A")
        return "N/A"

# Dummy-Funktion scanAndParse
def scanAndParse(entry, targetData):
    targetData.entries.append(entry)

# Hauptklasse BSR
class BSR:
    def __init__(self):
        self.restData = WasteData()
        self.recycleData = WasteData()
        self.bioData = WasteData()
        self.xmasData = WasteData()
        self.lastUpdate = None
        self.showHouseholdWaste = True
        self.showRecycleWaste = True
        self.showBioWaste = False
        self.showXmasWaste = True
        self.debugResponse = True
        self.bsrUrl = "https://www.bsr.de/abfuhrkalender"
        self.errorDeviceID = None

    def onStart(self):
        Domoticz.Log("BSR Plugin gestartet")
        # Suche !BSR Error! Device
        for d in Devices.values():
            if d.Name == "!BSR Error!":
                self.errorDeviceID = d.ID
                break
        if not self.errorDeviceID:
            Domoticz.Device(Name="!BSR Error!", Unit=1, Type=243, Subtype=1).Create()
            self.errorDeviceID = 1
        self.updateDevice(0, "No Data")

    def onHeartbeat(self):
        Domoticz.Debug("BSR: Heartbeat ausgelöst")
        self.readBsrWasteCollection()

    def updateDevice(self, nValue, sValue):
        if self.errorDeviceID and self.errorDeviceID in Devices:
            Devices[self.errorDeviceID].Update(nValue=nValue, sValue=sValue, AlwaysUpdate=True)

    def readBsrWasteCollection(self):
        try:
            if requests is None:
                self.updateDevice(4, "requests Modul fehlt")
                return

            r = requests.get(self.bsrUrl)
            now = datetime.now().date()

            if self.debugResponse:
                Domoticz.Debug(f"BSR Rohdaten: {r.content}")

            data = r.json().get("dates", {})

            for date_str, entries in data.items():
                for entry in entries:
                    category = entry.get("category", "")
                    service_date_str = entry.get("serviceDate_actual")
                    if not service_date_str:
                        continue
                    service_date = datetime.strptime(service_date_str, "%d.%m.%Y").date()
                    if service_date < now:
                        continue

                    if self.showHouseholdWaste:
                        scanAndParse(entry, self.restData)
                    if self.showRecycleWaste:
                        scanAndParse(entry, self.recycleData)
                    if self.showBioWaste:
                        scanAndParse(entry, self.bioData)

            if self.showXmasWaste:
                try:
                    rXmas = requests.get(self.bsrUrl + "?xmas=true")
                    soup = BeautifulSoup(rXmas.content, "html.parser")
                    for xmasTag in soup.find_all("li"):
                        scanAndParse(xmasTag, self.xmasData)
                except Exception as e:
                    Domoticz.Error(f"Fehler beim Abrufen von Weihnachtsdaten: {e}")

            Domoticz.Log(
                f"BSR: Haushaltsmüll {self.restData.getDate()} | "
                f"Gelber Sack {self.recycleData.getDate()} | "
                f"Bio {self.bioData.getDate()} | Xmas {self.xmasData.getDate()}"
            )

            self.updateDevice(0, "No Data")
            self.lastUpdate = datetime.now()

        except Exception as e:
            Domoticz.Error(f"BSR Exception: {e}")
            self.updateDevice(4, f"msg: {e}")
