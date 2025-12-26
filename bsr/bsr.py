# moved logic of to extra class
import re
import datetime as dtime
from datetime import timedelta
from time import mktime
import time as myTime

# import urllib
from urllib.parse import quote, quote_plus
import os

try:
    import Domoticz #python.analysis.warnings:
except ImportError:
    from blz import fakeDomoticz as Domoticz

from blz.blzHelperInterface import BlzHelperInterface

import sys
import traceback

try:
    from bs4 import BeautifulSoup
except Exception as e:
    Domoticz.Error("Error import BeautifulSoup".format(e))

try:
    import requests
except Exception as e:
    Domoticz.Error("Error import requests".format(e))

SHOW_ICON_IN_NAME = False
SHOW_ICON_IN_DETAIL = False
BSR_HOUR_THRESHOLD = 12  # o'clock when it is time to show next date


class WasteData:
    """small class that holds information for waste collection

    Returns:
        [type] -- [description]
    """

    def __init__(self, wasteType: str, category: str, show: bool = True):
        """init the waste data object

        Arguments:
            wasteType {str} -- type of this waste
            category {str} -- internal category used for this waste type

        Keyword Arguments:
            show {bool} -- if False, this type should not be shown (default: {True})
        """

        self.wasteDate = None
        self.wasteType = wasteType
        self.wasteHint = None
        self.category = category
        self.show = show
        self.wasteImage = None
        self.serviceDay = None
        self.servieDate_regular = None
        self.rhythm = None

    def getDate(self):
        return self.wasteDate

    def getType(self):
        return self.wasteType
    
    def getTypeLongName(self):
    # Falls kein Mapping existiert: nimm einfach den vorhandenen Text
        return Bsr.category_names.get(self.wasteType, self.wasteType)

    def getImage(self):
        return self.wasteImage

    def getHint(self):
        return self.wasteHint

    def isEmpty(self):
        return self.wasteDate is None

    def getShortStatus(self):
        """waste info (date) (hint)

        Returns:
            str -- status as text
        """

        return "{} {}".format(self.wasteDate, self.wasteHint)

    def getImageTag(self, size: str = "13", border: str = "1", align: str = ""):
        """generates an image tag based on the

        Keyword Arguments:
            size {str} -- height of the icon (default: {'13'})
            border {str} -- thickness of the board (default: {'1'})
            align {str} -- eg. top, works good on names (default: {''})

        Returns:
            {str} -- html image tag
        """
        i = ""
        if self.wasteImage is not None:
            i = (
                "<img src=https://www.bsr.de{} "
                "border={} height={} align={} >".format(
                    self.wasteImage, border, size, align
                )
            )
        return i

    def getLongStatus(self):
        """status information for this waste data.
        format (date) [optional image] (type) (hint)

        Returns:
            str -- the status as text/html
        """

        d = "- kein -"
        i = ""
        if self.wasteDate is not None:
            # use german format
            d = "{:%d.%m.%Y %a}: ".format(self.wasteDate)
        if self.wasteImage is not None and SHOW_ICON_IN_DETAIL is True:
            i = self.getImageTag(14)

        # Typenname holen (Biogut, Wertstoffe, Hausmüll…)
        type_text = self.getTypeLongName()

        # Farbe je nach Kategorie setzen
        try:
            from bsr.bsr import Bsr  # zyklische Imports vermeiden Domoticz-Fehler
        except ImportError:
            Bsr = None

        if Bsr is not None:
            color = Bsr.category_colors.get(self.category)
        else:
            color = None

        if color:
            type_text = "<span style='color:{};'>{}</span>".format(color, type_text)

        if self.wasteHint:
            hint_text = "(" + self.wasteHint + ")"
        else:
            hint_text = ""

        return "{} {} {} {}".format(d, i, type_text, hint_text)

    def isComplete(self):
        """if date is present this data is complete.
        Returns:
            bool -- true -> complete
        """
        return (
            self.wasteDate is None and self.show is False
        ) or self.wasteDate is not None


class Bsr(BlzHelperInterface):

    # now it is catergory
    BIO_CAT = "BI"
    RECYCLE_CAT = "WS"
    HOUSEHOLD_CAT = "HM"
    XMASTREE_CAT = "LT"

    category_names = {
    BIO_CAT: "Biogut",
    RECYCLE_CAT: "Wertstoffe",
    HOUSEHOLD_CAT: "Hausmüll",
    XMASTREE_CAT: "Weihnachtsbaum"
}
    # NEU: Farben für die Ausgabe
    category_colors = {
        BIO_CAT: "green",      # Biogut
        RECYCLE_CAT: "orange", # Wertstoffe 
        HOUSEHOLD_CAT: "black",   #Hausmüll
        XMASTREE_CAT: "darkgreen",   #Weihnachtbaum
    }

    def __init__(
        self,
        street: str,
        zipCode: str,
        houseNumber: str,
        showHouseholdWaste: bool = True,
        showRecycleWaste: bool = True,
        showBioWaste: bool = True,
        showXmasWaste: bool = False,
        debugResponse: bool = False,
    ):
        """init the bsr object. With that you can access data from bsr website.

        Arguments:
            street {str} -- street name
            zipCode {str} -- post code
            houseNumber {str} -- house number

        Keyword Arguments:
            showHouseholdWaste {bool} -- turn on/off normal waste  (default: {True})
            showRecycleWaste {bool} -- turn on/off plastic waste (default: {True})
            showBioWaste {bool} -- turn on/off bio waste (default: {True})
            showXmasWaste {bool} -- turn on/off xmas tree (default: {False})
            debugResponse {bool} -- turn on/off output of response from bsr website  (default: {False})
        """
        self.showHouseholdWaste = showHouseholdWaste
        self.showRecycleWaste = showRecycleWaste
        self.showBioWaste = showBioWaste
        self.showXmasWaste = showXmasWaste
        self.debugResponse = debugResponse
        self.bsrUrl = "https://www.bsr.de/abfuhrkalender"
        self.street = street
        self.number = houseNumber
        self.zip = zipCode
        self.lastUpdate = dtime.datetime.now()
        self.debug = False
        self.error = False
        self.nextpoll = dtime.datetime.now()
        self.reset()
        return

    def needsUpdate(self):
        """does some of the devices need an update

        Returns:
            boolean -- if True -> please update the device in domoticz
        """

        return self.needUpdate

    def dumpConfig(self):
        """just print configuration and settings to log"""
        self.dumpBsrConfig()

    def dumpBsrConfig(self):
        """just print configuration and settings to log"""

        Domoticz.Debug(
            "houshold: {}\trecycle: {}\tbio: {}\txmas: {}\n\r"
            "\tstreet:\t{} {}\tzip:\t{}, debugResponse:\t{}".format(
                self.showHouseholdWaste,
                self.showRecycleWaste,
                self.showBioWaste,
                self.showXmasWaste,
                self.street,
                self.number,
                self.zip,
                self.debugResponse,
            )
        )

    def reset(self):
        """set all important fields to None"""
        self.nearest = None
        self.location = None
        self.initWasteData()
        self.nextCollectionDate = None
        self.nextCollectionName = None
        self.nextCollectionHint = None
        self.observationDate = None
        self.needUpdate = True
        self.resetError()

    def reinitData(self):
        self.initWasteData()

    def initWasteData(self):
        """re-init waste date objects"""

        self.restData = WasteData(
            "Restmuell", Bsr.HOUSEHOLD_CAT, self.showHouseholdWaste
        )
        self.recycleData = WasteData(
            "Wertstoffe", Bsr.RECYCLE_CAT, self.showRecycleWaste
        )
        self.bioData = WasteData("Bio", Bsr.BIO_CAT, self.showBioWaste)
        self.xmasData = WasteData(
            "Weihnachtsbaum", Bsr.XMASTREE_CAT, self.showXmasWaste
        )

    def dumpStatus(self):
        self.dumpBsrStatus()

    def dumpBsrStatus(self):
        """just print current status to log"""

        Domoticz.Log(
            "##########################################\n"
            "{}:\nMüll:\t{}\n\r"
            "Recycle:\t{}\n\r"
            "Bio:\t{}\n\r"
            "Weihnachtsbaum:\t{}\n\r"
            "nextCollection:\t{}-{} {}\n\r"
            "need update?:\t{}".format(
                self.location,
                self.restData.getShortStatus(),
                self.recycleData.getShortStatus(),
                self.bioData.getShortStatus(),
                self.xmasData.getShortStatus(),
                self.nextCollectionDate,
                self.nextCollectionName,
                self.nextCollectionHint,
                #  self.observationDate,
                self.needUpdate,
            )
        )

    def getAlarmLevel(self):
        """calculates alarm level based on nearest waste element

        Returns:
            {int} -- alarm level
        """

        alarm = 0
        if self.hasError is False:
            dt = self.getNearestDate()
            lvl = calculateAlarmLevel(dt)
            alarm = lvl[0]
        else:
            alarm = 5
        return alarm

    def getAlarmText(self):
        """only returns latest element like: (date) [optional hint]
        if you want more, look at getSummary()

        Returns:
            {str} -- data from nearest text
        """

        s = "No Data"
        if self.hasError is False and self.nearest is not None:
            hint = self.nearest.getHint()
            s = "{}{}".format(self.nearest.getDate(), hint if hint is not None else "")
        if self.hasError is True:
            s = "Error to get data"
        return s

    def getDeviceName(self):
        """Name basierend auf allen Abfallarten am nächsten Termin.
        Beispiel: 'Hausmüll und Biogut (3 Tage)'
        """

        s = "No Data"
        if self.hasError:
            return "!Error!"

        if self.nearest is None or self.nearest.getDate() is None:
            return s

        nearest_date = self.getNearestDate()

        # Alle Objekte, die an diesem Datum abgeholt werden
        same_day = []
        for obj in (self.restData, self.recycleData, self.bioData, self.xmasData):
            if obj and obj.getDate() == nearest_date:
                same_day.append(obj.getTypeLongName())

        # Doppelte entfernen, Reihenfolge beibehalten
        seen = set()
        unique_types = []
        for t in same_day:
            if t not in seen:
                seen.add(t)
                unique_types.append(t)

        if not unique_types:
            # Fallback: alter Mechanismus
            t = self.nearest.getTypeLongName()
        else:
            t = " und ".join(unique_types)

        # Klammern o.ä. aus dem Namen rausnehmen, damit der Titel kurz bleibt
        t = re.sub(r"[\(\[].*?[\)\]]", "", t).strip()

        # Tage-Text holen (z.B. '(3 Tage)', '(Morgen!)' etc.)
        lvl = calculateAlarmLevel(nearest_date)
        days_txt = lvl[1]

        # Kein HTML im Gerätenamen, nur Text
        s = "{} {}".format(t, days_txt).strip()

        return s
    
    def getNearestDate(self):
        d = None
        if self.nearest is not None:
            d = self.nearest.getDate()
        return d

    def checkForNearest(self, dt: WasteData):
        """takes given data and put in store, if this on is important for alarm level self.
        therefore search for smallest date. BUT this must be at least today.
        Arguments:
            dt {WasteData} -- the data to verify
        """
        now = dtime.datetime.now().date()
        if dt is None or dt.getDate() is None:
            return
        h = dtime.datetime.now().hour
        d = dtime.datetime.now().date()
        if (
            dt.getDate() == dtime.datetime.now().date()
            and dtime.datetime.now().hour < BSR_HOUR_THRESHOLD
        ) or dt.getDate() > dtime.datetime.now().date():

            if self.nearest is None:
                self.nearest = dt
            elif self.nearest.getDate() > dt.getDate():
                self.nearest = dt
        else:
            Domoticz.Debug(
                "{} It's after threshold ..., ignore it".format(dt.getDate())
            )

    def timeToShowXms(self):
        """checks if it's time to show xmas tree collection dataself.
           It must be December or January.
        Returns:
            bool -- True or False
        """
        if dtime.datetime.now().month == 12 or dtime.datetime.now().month == 1:
            return True
        else:
            return False

    def getSummary(self, seperator: str = "<br>"):
        from collections import defaultdict
        from datetime import date as _date

        customObjects = []

        if self.showHouseholdWaste:
            customObjects.append(self.restData)
        if self.showRecycleWaste:
            customObjects.append(self.recycleData)
        if self.showBioWaste:
            customObjects.append(self.bioData)
        if self.showXmasWaste and self.timeToShowXms():
            customObjects.append(self.xmasData)

        # Leere ausschließen & sortieren
        customObjects = [o for o in customObjects if o.wasteDate]
        customObjects.sort(key=lambda x: x.wasteDate)

        grouped = defaultdict(list)
        for obj in customObjects:
            grouped[obj.wasteDate].append(obj)

        lines = []
        for date_key in sorted(grouped.keys()):
            objs = grouped[date_key]

            # Datum formatieren
            date_str = date_key.strftime("%d.%m.%Y %a")

            # Typen farbig rendern
            type_parts = []
            for o in objs:
                color = Bsr.category_colors.get(o.category, None)
                name = o.getTypeLongName()
                if color:
                    type_parts.append(f"<span style='color:{color};font-weight:bold;'>{name}</span>")
                else:
                    type_parts.append(name)

            types_joined = " und ".join(type_parts)

            # Hinweise (falls vorhanden)
            hints = [f"({o.getHint()})" for o in objs if o.getHint()]
            hint_str = " ".join(hints)

            lines.append(f"{date_str}: {types_joined} {hint_str}".strip())

        return seperator.join(lines) if lines else "Keine Termine gefunden"

        if not lines:
            return "Keine Termine gefunden"

        return seperator.join(lines)

    def setError(self, error):
        """sets the error msg and put error flag to True

        Arguments:
            error {Exception} -- the caught exception
        """
        self.hasError = True
        self.errorMsg = error

    def hasErrorX(self):
        return self.hasError

    def getErrorMsg(self):
        """
        if there is an error message, this will be delivered
        """
        return self.errorMsg

    def resetError(self):
        """just removes error flag and deletes last error msg"""
        self.hasError = False
        self.errorMsg = None

    # convert module to python source filename
    def _py_source(self, module):
        path = module.__file__
        if path[:-1].endswith("py"):
            path = path[:-1]
        return path

    def requestWasteData(self, xMas: bool = False):
        Domoticz.Debug("Retrieve waste collection data from " + self.bsrUrl)

        r = requests.get(self.bsrUrl)
        

        s = requests.Session()
        s.get(self.bsrUrl)

        # 1: get street
        url = "https://umnewforms.bsr.de/p/de.bsr.adressen.app/streetNames/?searchQuery={}".format(
            self.street
        )
       
        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.bsr.de/",
        }
        r = s.get(url, headers=headers)
        data = r.json()
        # TODO check status
        Domoticz.Debug("BSR: #2 working Streets:\t")
        relevantStreet = None

        if len(data) > 1:
            Domoticz.Log("Found more than one street - try to guess ...")
            for street in data:
                # TODO wenn mehrere Strassen mit selber plz go deeper, check name
                if self.zip in street["value"]:
                    relevantStreet = street
                    Domoticz.Debug("found street:\t{}".format(street))
                    break

        else:
            relevantStreet = data[0]

        if relevantStreet is None:
            raise Exception("Did not find a relevant street")
        # transform to bst like street
        bsrParamRelvStreet = convertUrl(relevantStreet["value"])

        bsrQueryRelvStreet = convert4Query(relevantStreet["value"])
        Domoticz.Debug(
            "using for bsr street:\t'{}'\t'{}'".format(
                bsrParamRelvStreet, bsrQueryRelvStreet
            )
        )

        # 2: get results for street and house number
        url = (
            "https://umnewforms.bsr.de/p/de.bsr.adressen.app//plzSet/plzSet?searchQuery={}:::{}"
            .format(bsrParamRelvStreet, self.number)
        )
        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "Referer": "https://www.bsr.de/",
        }
        r = s.get(url, headers=headers)
        json = r.json()
        Domoticz.Debug("BSR: #3 scan results based on street an number -> check zip code:\t")
        relevant_item = None
        relevantNumber = None

        relevant_item = next((item for item in json if self.zip in item["label"]), None)

        # Extract the value
        relevantNumber = relevant_item["value"] if relevant_item else None

        # Print matching items
        Domoticz.Debug("found nr:\t{}".format(relevant_item))
        
        if len(json) > 1:
            Domoticz.Log("Found more than one number - tried to guess on zip code ...")
        
        # Print matching items
        Domoticz.Debug("found nr:\t{}".format(relevant_item))
      
        if relevantNumber is None:
            raise Exception("Did not find a relevant number")
        
        # Get today's date and date 4 weeks ahead
        today = dtime.datetime.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday = 0
        four_weeks_later = today + timedelta(weeks=4)

        # Format dates in the required format: yyyy-MM-ddTHH:mm:ss
        date_from_str = start_of_week.strftime("%Y-%m-%dT00:00:00")

        date_to_str = four_weeks_later.strftime("%Y-%m-%dT00:00:00")

        # categroies: HM = Hausmüll, BI=Bio, WS=Wertstoffe LT=? maybe xmas?
        # Build the URL
        url = (
            f"https://umnewforms.bsr.de/p/de.bsr.adressen.app/abfuhrEvents?"
            f"filter=AddrKey%20eq%20%27{relevantNumber}%27%20"
            f"and%20DateFrom%20eq%20datetime%27{date_from_str}%27%20"
            f"and%20DateTo%20eq%20datetime%27{date_to_str}%27%20"
            f"and%20(Category%20eq%20%27HM%27%20or%20Category%20eq%20%27BI%27%20or%20Category%20eq%20%27WS%27%20or%20Category%20eq%20%27LT%27)"
        )

        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "Referer": "https://www.bsr.de/",
        }
        # TODO 
        # done dates
        # add catergories eg for xmas?
        
        # BSR use same query for xmas trees but, returns only those!
        if xMas is True:
            abf_config_weihnachtsbaeume = "on"
        else:
            abf_config_weihnachtsbaeume = ""
       
        # Domoticz.Debug("data: {}".format(data))
        r = s.get(url, headers=headers)
        return r
       

    def readBsrWasteCollection(self):
        """tries to get  data from bsr and parse it.
        Values are stored on attributes.
        check self.needUpdate. if we get new data we set a flag there.
        """

        try:
            # Wichtig: bei jedem Poll alten Zustand verwerfen,
            # sonst bleibt "nearest" nach einem abgelaufenen Termin hängen.
            self.nearest = None
            self.reinitData()   # setzt rest/recycle/bio/xmas auf leer
            self.needUpdate = True
            # Domoticz.Debug('Retrieve waste collection data from ' + self.bsrUrl)
            r = self.requestWasteData()
            # Today (just date, no time part)
            now = dtime.datetime.now().date()

            Domoticz.Debug("BSR: #4 Parse Data (without Xmas")
            if self.debugResponse is True:
                Domoticz.Debug("data: {}".format(r.content))


            # Collect invalid entries (if any)
            invalid_entries = []

            # Define the valid categories
            valid_categories = {"HM", "BI", "WS", "LT"}

            # Loop through all date entries
            for date_str, entries in r.json()["dates"].items():
                for entry in entries:
                    category = entry.get("category")
                    if category not in valid_categories:
                        invalid_entries.append({
                            "reason": "unknwon category",
                            "date": date_str,
                            "category": category,
                            "entry": entry
                        })
                        continue
                    
                    # check date
                    service_date_str = entry.get("serviceDate_actual")
                    if service_date_str == None:
                        invalid_entries.append({
                            "reason": "date is empty",
                            "date": date_str,
                            "category": category,
                            "entry": entry
                        })
                        continue
        # robustes Parsen ohne datetime.strptime (stabil bei Plugin-Restarts)
                    t = myTime.strptime(service_date_str, "%d.%m.%Y")
                    service_date = dtime.date(t.tm_year, t.tm_mon, t.tm_mday)
                    #service_date = _date(t.tm_year, t.tm_mon, t.tm_mday)                   ggf. löschen

        # Termine in der Vergangenheit immer verwerfen
                    if service_date < now:
                        continue

        # Heute nur bis zur Uhrzeit-Schwelle gültig
                    #if service_date == now and datetime.now().hour >= BSR_HOUR_THRESHOLD:    ggf. löschen
                    if service_date == now and dtime.datetime.now().hour >= BSR_HOUR_THRESHOLD:
                        continue

                    # take  care about it:
                    if self.showHouseholdWaste is True:
                        scanAndParse(entry, self.restData)
                        self.checkForNearest(self.restData)
                    
                    if self.showRecycleWaste is True:
                        scanAndParse(entry, self.recycleData)
                        self.checkForNearest(self.recycleData)

                    if self.showBioWaste is True:
                        scanAndParse(entry, self.bioData)
                        self.checkForNearest(self.bioData)
                    
                    if self.showXmasWaste and self.timeToShowXms():
                        scanAndParse(entry, self.xmasData)
                        self.checkForNearest(self.xmasData)

                    # if we have all data, leave loop
                    if (
                        self.restData.isComplete() is True
                        and self.recycleData.isComplete() is True
                        and self.bioData.isComplete() is True
                        and (not self.showXmasWaste or self.xmasData.isComplete())
                    ):
                        break
            Domoticz.Log(
                "BSR: #4.4\t gelber Sack {}\tHausmuell {} ".format(
                    self.recycleData.getDate(), self.restData.getDate()
                )
            )
                        
            # Output results
            if invalid_entries:
                Domoticz.Error("Invalid category entries found:")
                for item in invalid_entries:
                    Domoticz.Error(f"Date: {item['date']}, Category: {item['category']},  Reason: {item['reason']}")
            else:
                Domoticz.Debug("✅ All entries have valid categories.")

            # TODO -> check for error?
            # error = soup.find("li", {"class": "abf_errormsg"})
            error = None
            if error is not None:
                Domoticz.Log("Could not load waste collection data. Raise exception")
                self.setError(error)
                raise Exception("Could not load data - verify settings")
            else:
                self.resetError()
            self.lastUpdate = dtime.datetime.now()
        except Exception as e:
            Domoticz.Error("BSR EXCEPTION: {}".format(e))
            Domoticz.Error("BSR TRACEBACK:\n{}".format(traceback.format_exc()))
            self.setError(str(e))
            return


#############################################################################
#                       Data specific functions                             #
#############################################################################


def calculateAlarmLevel(wasteDate):
    """takes an waste element and calculates the domoticz alarm level

    Arguments:
        wasteDate {[type]} -- the element to check

    Returns:
        [{int}, text ]-- alarm level and text holding the days till date
    """

    level = 1
    smallerTxt = ""
    if wasteDate is not None:
        delta = wasteDate - dtime.datetime.now().date()
        # Level = (0=gray, 1=green, 2=yellow, 3=orange, 4=red)
        if delta.days <= 1:
            level = 4
        elif delta.days == 2:
            level = 3
        elif delta.days == 3:
            level = 2
        else:
            level = 0

        if delta.days == 2:
            smallerTxt = "{} ({})".format(smallerTxt, "Übermorgen")
        elif delta.days == 1:
            smallerTxt = "{} ({}!)".format(smallerTxt, "Morgen")
        elif delta.days == 0:
            smallerTxt = "{} ({}!!!)".format(smallerTxt, "Heute")
        else:
            smallerTxt = "{} ({} Tage)".format(smallerTxt, delta.days)
    return [level, smallerTxt]


def scanAndParse(entry, wasteData: WasteData):
    # JSON-Parser (kein HTML mehr)

    # Nur parsen, wenn dieser Abfalltyp noch leer ist und die Kategorie passt
    if not (wasteData.isEmpty() and entry.get("category") == wasteData.category):
        return wasteData

    Domoticz.Debug("found matching entry for {}".format(wasteData.wasteType))

    service_date_str = entry.get("serviceDate_actual")
    if not service_date_str:
        Domoticz.Debug("Skip entry, no date... {}".format(service_date_str))
        return wasteData

    # Restart-sicher: dd.mm.yyyy manuell splitten und datetime.date aus Stdlib holen
    try:
        d, m, y = service_date_str.split(".")
        import importlib
        _dt = importlib.import_module("datetime")
        wasteData.wasteDate = _dt.date(int(y), int(m), int(d))
    except Exception as e:
        import traceback
        Domoticz.Error(
            "Could not parse content -> data {}\tentry {} ... exc: {} ".format(
                wasteData, entry, e
            )
        )
        Domoticz.Error("TRACE:\n{}".format(traceback.format_exc()))
        return wasteData

    # Restliche Felder übernehmen
    wasteData.wasteType = entry.get("category")
    wasteData.wasteHint = entry.get("warningText")
    wasteData.serviceDay = entry.get("serviceDay")
    wasteData.servieDate_regular = entry.get("serviceDate_regular")
    wasteData.rhythm = entry.get("rhythm")

    return wasteData

def getDate(sDate: str, sFormat: str):
    """Parse string to date object.
    Trying it with dtime.datetime.strptime or time.strptime
    Helps walking around different domoticz behavior between
    start up and update.
    Arguments:
        sDate {str} -- the date as string
        sFormat {str} -- format eg. '%Y-%m-%d'
    Returns:
        [date] -- none or the date object
    """
    dt = getDatetime(sDate, sFormat)
    myDate = None
    if dt is not None:
        myDate = dt.date()
    # Domoticz.Debug(res)
    return myDate


def getDatetime(sDate: str, sFormat: str):
    """Parse string to datetime object.
        Trying it with dtime.datetime.strptime or time.strptime
    Helps walking around different domoticz behavior between
    start up and update.
    Arguments:
        sDate {str} -- the date as string
        sFormat {str} -- format eg. '%Y-%m-%d'
    Returns:
        [datetime] -- none or the datetime object
    """
    dt = None
    myDate = None
    try:
        dt = dtime.datetime.strptime(sDate, sFormat)
    except TypeError:
        dt = datetime(*(myTime.strptime(sDate, sFormat)[0:6]))
    return dt


def convertUrl(parameter: str):
    """replaces white spaces with%20 to work in urls

    Arguments:
        parameter {str} -- the value of the string to convert

    Returns:
        str -- string with replaced ' '
    """
    s = quote(parameter)
    return s


def convert4Query(parameter: str):
    """replaces ',' with '%2C' and ' ' with '+' to work with bsr query parameter

    Arguments:
        parameter {str} -- the string to parse

    Returns:
        [type] -- str
    """
    s = quote_plus(parameter)
    return s
