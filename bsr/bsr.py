# moved logic of to extra class
import re
from datetime import datetime, timedelta
from time import mktime
import time as myTime

# import urllib
from urllib.parse import quote, quote_plus
import os

# import locale, breaks domoticz on synology ...
# try:
#    locale.setlocale(locale.LC_ALL, "de_DE.utf8")
#    # locale.setlocale(locale.LC_TIME, "de") # german
# except locale.Error:
#    Domoticz.Error("Cannot set locale.")

try:
    import Domoticz #python.analysis.warnings:
except ImportError:
    from blz import fakeDomoticz as Domoticz

from blz.blzHelperInterface import BlzHelperInterface

import sys

# sys.path
# sys.path.append('/volume1/@appstore/py3k/usr/local/lib/python3.5/site-packages')
# sys.path.append('C:\\Program Files (x86)\\Python37-32\\Lib\\site-packages')

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
        return Bsr.category_names.get(self.wasteType)

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
        # we do it in non proper way. Otherwise Update Name will fail on Domoticz.
        # "src='sdsd' foo bar --> leads to invalid sql"
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
            # d = "{:%Y-%b-%d %a}: ".format(self.wasteDate)
            # use german format
            d = "{:%d.%m.%Y %a}: ".format(self.wasteDate)
        if self.wasteImage is not None and SHOW_ICON_IN_DETAIL is True:
            i = self.getImageTag(14)
        return "{} {} {} {}".format(
            d,
            i,
            # '-' if self.wasteDate is None else self.wasteDate,
            self.getTypeLongName(),
            "" if self.wasteHint is None else "(" + self.wasteHint + ")",
        )

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
        self.lastUpdate = datetime.now()
        self.debug = False
        self.error = False
        self.nextpoll = datetime.now()
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
        """calculates a name based on nearest waste element
        form: [image optional] (waste type) (days till collection)

        Returns:
            {str} -- name as string
        """

        s = "No Data"
        if self.nearest is not None:
            dt = self.getNearestDate()
            lvl = calculateAlarmLevel(dt)
            days = lvl[1]
            img = ""
            if SHOW_ICON_IN_NAME is True:
                img = "{}".format(self.nearest.getImageTag("22", "0", "top"))
            t = self.nearest.getTypeLongName()
            # remove () from type to keep title short
            t = re.sub("[\(\[].*?[\)\]]", "", t)
            s = "{} {} {}".format(img, t, lvl[1])

        if self.hasError is True:
            s = "!Error!"
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
        now = datetime.now().date()
        if dt is None or dt.getDate() is None:
            return
        h = datetime.now().hour
        d = datetime.now().date()
        if (
            dt.getDate() == datetime.now().date()
            and datetime.now().hour < BSR_HOUR_THRESHOLD
        ) or dt.getDate() > datetime.now().date():

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
        if datetime.now().month == 12 or datetime.now().month == 1:
            return True
        else:
            return False

    def getSummary(self, seperator: str = "<br>"):

        customObjects = []
        summary = ""
        if self.showHouseholdWaste:
            customObjects.append(self.restData)
        if self.showRecycleWaste:
            customObjects.append(self.recycleData)
        if self.showBioWaste:
            customObjects.append(self.bioData)
        if self.showXmasWaste is True and self.timeToShowXms() is True:
            customObjects.append(self.xmasData)

        # One line sort function method using an inline lambda function lambda x: x.date
        # The value for the key param needs to be a value that identifies the sorting property on the object
        customObjects.sort(
            key=lambda x: x.wasteDate if (x and x.wasteDate) else datetime.now().date(),
            reverse=False,
        )
        for obj in customObjects:
            Domoticz.Debug("Sorted: " + str(obj.wasteDate) + ":  " + obj.wasteType)
            summary = summary + obj.getLongStatus() + seperator
        return summary

    # check which date is smaller
    # if ((result[0] and result[1]) and result[0] < result[1] ) or (result[0] and not result[1]):
    #     smallerDate = result[0]
    #     smallerTxt = 'MÃ¼ll {}'.format( smallerDate );
    # elif (result[0] and result[1]) and result[0] > result[1] or (not result[0] and result[1]):
    #     smallerDate = result[1]
    #     smallerTxt = 'Gelber Sack {}'.format( smallerDate );
    # else:
    #     smallerDate = None
    #     smallerTxt = 'FEHLER';

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
        today = datetime.today()
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
            # Domoticz.Debug('Retrieve waste collection data from ' + self.bsrUrl)
            r = self.requestWasteData()
            # Today (just date, no time part)
            now = datetime.now().date()

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
                    service_date = datetime.strptime(service_date_str, "%d.%m.%Y").date()
                    if service_date <= now:
                        invalid_entries.append({
                            "reason": "serviceDate_actual not in future",
                            "date": date_str,
                            "category": category,
                            "entry": entry
                        })
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

                    # if we have all data, leave loop
                    if (
                        self.restData.isComplete() is True
                        and self.recycleData.isComplete() is True
                        and self.bioData.isComplete() is True
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
                # reset data store
                # self.initWasteDate()
                # do not reset, we just got fresh data ... self.reset()
            
            # TODO
            # if self.showXmasWaste and self.timeToShowXms() is True:
            #     Domoticz.Debug("BSR: #5.1 Read Xmas Data")
            #     rXmas = self.requestWasteData(xMas=True)
            #     Domoticz.Debug("BSR: #5.2 Parse Data (without Xmas")
            #     if self.debugResponse is True:
            #         Domoticz.Debug("data: {}".format(rXmas.content))
            #     soup = BeautifulSoup(rXmas.content, "html.parser")

            #     for xmasTag in soup.find_all("li"):
            #         scanAndParse(xmasTag, self.xmasData)
            #         self.checkForNearest(self.xmasData)

            #         if self.xmasData.isComplete() is True:
            #             break
            # only set last Update time if success
            self.lastUpdate = datetime.now()
        except (Exception) as e:
            Domoticz.Error("Error: {} used paths: {} ".format(e, sys.path))
            self.setError(e)
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
        delta = wasteDate - datetime.now().date()
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
    image = None
    now = datetime.now().date()
    try:
        image = tag.find("img")
    except Exception as e:
        pass
    if (
        wasteData.isEmpty()
        and entry['category'] == wasteData.category 
        ): 
        Domoticz.Debug("found matching entry for {}".format(wasteData.wasteType))
        try:
            
            if entry['serviceDate_actual'] is not None :
                service_date = datetime.strptime( entry['serviceDate_actual'], "%d.%m.%Y").date()
                wasteData.wasteDate = service_date
                wasteData.wasteType = entry['category']
                wasteData.wasteHint = entry['warningText']
                if image is not None:
                    wasteData.wasteImage = image["src"]
                    Domoticz.Debug("img: {}".format(image))
            else:
                Domoticz.Debug("Skip entry,no date... {}".format(entry['serviceDate_actual']))
            
        except Exception as e:
            Domoticz.Error(
                "Could not parse content -> data {}\tentry {} ... exc: {} ".format(
                    wasteData, entry, e
                )
            )
    return wasteData

def getDate(sDate: str, sFormat: str):
    """Parse string to date object.
    Trying it with datetime.strptime or time.strptime
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
        Trying it with datetime.strptime or time.strptime
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
        dt = datetime.strptime(sDate, sFormat)
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
    # return parameter.replace(",", "%2C").replace(" ", "+")


# def verifyBS4():
#     if(moduleLoaded('bs4') is False):
#         try:
#             from bs4 import BeautifulSoup
#         except Exception as e:
#             Domoticz.Error("Error import BeautifulSoup".format(e))


# def moduleLoaded(modulename: str):
#     import sys
#     if modulename not in sys.modules:
#         Domoticz.Error('{} not imported'.format(modulename))
#         return False
#     else:
#         Domoticz.Debug('{}: {}'.format(modulename, sys.modules[modulename]))
#         return True
