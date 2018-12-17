# moved logic of meteo rss warning to extra class
import sys
sys.path
sys.path.append('/usr/lib/python3/dist-packages')
sys.path.append('/volume1/@appstore/py3k/usr/local/lib/python3.5/site-packages')
sys.path.append('C:\\Program Files (x86)\\Python37-32\\Lib\\site-packages')
from bs4 import BeautifulSoup
import re
import requests
from datetime import datetime, timedelta
from time import mktime
import time as myTime
import locale
try:
    locale.setlocale(locale.LC_ALL, "de_DE.utf8")
    # locale.setlocale(locale.LC_TIME, "de") # german
except locale.Error:
    Domoticz.Error("Cannot set locale.")
import urllib

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz


class WasteData:
    def __init__(self, wasteType: str, divClass: str, show: bool = True):
        self.wasteDate = None
        self.wasteType = wasteType
        self.wasteHint = None
        self.divClass = divClass
        self.show = show

    def getDate(self):
        return self.wasteDate

    def getType(self):
        return self.wasteType

    def getHint(self):
        return self.wasteHint

    def isEmpty(self):
        return self.wasteDate is None

    def getShortStatus(self):
        return "{} {}".format(self.wasteDate, self.wasteHint)

    def getLongStatus(self):
        d = "- kein -"
        if(self.wasteDate is not None):
            d = "{:%Y-%b-%d %a}: ".format(self.wasteDate)
        return "{} {} {}".format(
            d,
            # '-' if self.wasteDate is None else self.wasteDate,
            self.wasteType,
            '' if self.wasteHint is None else "(" + self.wasteHint + ")")

    def isComplete(self):
        return (self.wasteDate is None and self.show is False) or self.wasteDate is not None


class Bsr:

    # span class used by bsr to mark dif. waste typea
    BIO_CLASS = "Biogut"
    RECYCLE_CLASS = "WertstoffeAlba"
    HOUSEHOLD_CLASS = "Restmuell"

    def __init__(self,
                 street: str, zipCode: str, houseNumber: str,
                 showHouseholdWaste: bool = True,
                 showRecycleWaste: bool = True,
                 showBioWaste: bool = True

                 ):
        self.showHouseholdWaste = showHouseholdWaste
        self.showRecycleWaste = showRecycleWaste
        self.showBioWaste = showBioWaste
        self.bsrUrl = "https://www.bsr.de/abfuhrkalender-20520.php"
        self.street = street
        self.number = houseNumber
        self.zip = zipCode
        self.lastUpdate = datetime.now()
        self.debug = False
        self.error = False
        self.nextpoll = datetime.now()
        self.reset()
        return

    def needUpdate(self):
        '''does some of the devices need an update

        Returns:
            boolean -- if True -> please update the device in domoticz
        '''

        return self.needUpdate

    def dumpBsrConfig(self):
        '''just print configuration and settings to log
        '''

        Domoticz.Debug(
            "houshold: {}\trecycle: {}\tbio: {}\n\r"
            "\tstreet:\t{} {}\tzip:\t{}"
            .format(
                self.showHouseholdWaste,
                self.showRecycleWaste,
                self.showBioWaste,
                self.street,
                self.number,
                self.zip
            )
        )

    def reset(self):
        '''set all importent fields to None
        '''

        self.nearest = None

        self.location = None
        self.restData = WasteData("Restmuell", Bsr.HOUSEHOLD_CLASS, self.showHouseholdWaste)
        self.recycleData = WasteData("Wertstoffe", Bsr.RECYCLE_CLASS, self.showRecycleWaste)
        self.bioData = WasteData("Bio", Bsr.BIO_CLASS, self.showBioWaste)
        self.nextCollectionDate = None
        self.nextCollectionName = None
        self.nextCollectionHint = None
        self.observationDate = None
        self.needUpdate = True

    def dumpBsrStatus(self):
        '''just print current status to log
        '''

        Domoticz.Log(
            "##########################################\n"
            "{}:\nMüll:\t{}\n\r"
            "Recycle:\t{}\n\r"
            "Bio:\t{}\n\r"
            "nextCollection:\t{}-{} {}\n\r"
            "need update?:\t{}"
            .format(
                self.location,
                self.restData.getShortStatus(),
                self.recycleData.getShortStatus(),
                self.bioData.getShortStatus(),
                self.nextCollectionDate,
                self.nextCollectionName,
                self.nextCollectionHint,
                #  self.observationDate,
                self.needUpdate
            )
        )

    def getAlarmLevel(self):
        alarm = 0
        if(self.hasError is False):
            dt = self.getNearestDate()
            lvl = calculateAlarmLevel(dt)
            alarm = lvl[0]
        else:
            alarm = 5
        return alarm

    def getAlarmText(self):
        s = "No Data"
        if(self.hasError is False and self.nearest is not None):
            hint = self.nearest.getHint()
            s = "{}{}".format(self.nearest.getDate(), hint if hint is not None else "")
        if(self.hasError is True):
            s = "Error to get data"
        return s

    def getDeviceName(self):
        s = "No Data"
        if(self.nearest is not None):
            dt = self.getNearestDate()
            lvl = calculateAlarmLevel(dt)
            days = lvl[1]
            s = "{} {}".format(self.nearest.getType(), lvl[1])
        if(self.hasError is True):
            s = "Error"
        return s

    def getNearestDate(self):
        d = None
        if(self.nearest is not None):
            d = self.nearest.getDate()
        return d

    def checkForNearest(self, dt: WasteData):
        '''takes given data and put in store, if this on is importent for alarm levelself.
        therefore search for smallest date.
        Arguments:
            dt {WasteData} -- the data to verify
        '''

        if(dt is None or dt.getDate() is None):
            return
        if(self.nearest is None):
            self.nearest = dt
            return
        if(dt is not None and dt.getDate() is not None):
            # check deeper
            if(dt.getDate() < self.nearest.getDate()):
                self.nearest = dt

    def getSummary(self, seperator: str = '<br>'):

        customObjects = []
        summary = ""
        if self.showHouseholdWaste:
            customObjects.append(self.restData)
        if self.showRecycleWaste:
            customObjects.append(self.recycleData)
        if self.showBioWaste:
            customObjects.append(self.bioData)
        # One line sort function method using an inline lambda function lambda x: x.date
        # The value for the key param needs to be a value that identifies the sorting property on the object
        customObjects.sort(key=lambda x: x.wasteDate
            if(x and x.wasteDate) else datetime.now().date(), reverse=False)
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
        self.hasError = True
        self.errorMsg = error

    def resetError(self):
        self.hasError = False
        self.errorMsg = None

    def readBsrWasteCollection(self):
        """tries to get rss data from meteo and parse it.
        Values are stored on attributes.
        check self.needUpdate. if we get new data we set a flag there.
        """

        try:
            Domoticz.Debug('Retrieve waste collection data from ' + self.bsrUrl)

            r = requests.get('https://www.bsr.de/abfuhrkalender-20520.php')
            # cookie = {'PHPSESSID': r.cookies['PHPSESSID']}
            # Domoticz.Debug('BSR-R: ' + str(r) )
            # Domoticz.Debug('BSR-C: ' + str(cookie) )
            url = 'https://www.bsr.de/abfuhrkalender_ajax.php?script=dynamic_kalender_ajax'
            formdata = {'abf_strasse': 'Germanenstr.',
                        'abf_hausnr': '30D',
                        'tab_control': 'Liste',
                        'abf_config_weihnachtsbaeume': '',
                        'abf_config_restmuell': 'on',
                        'abf_config_biogut': 'on',
                        'abf_config_wertstoffe': 'on',
                        'abf_config_laubtonne': 'on',
                        'abf_selectmonth': '11+2018',
                        'abf_datepicker': '30.10.2018',
                        'listitems': '7'}

            # &abf_strasse=Germanenstr.&abf_hausnr=30D&tab_control&abf_config_weihnachtsbaeume=&abf_config_restmuell=on&abf_config_biogut=on&abf_config_wertstoffe=on&abf_config_laubtonne=on&abf_selectmonth=11+2018&abf_datepicker=04.11.2018&listitems=1'
            # r# = requests.post(url, data = {'key':'value'}, cookies=cookie)
            # Domoticz.Debug( str(r.content) )

            s = requests.Session()
            s.get('https://www.bsr.de/abfuhrkalender-20520.php')

            # 1: get street
            # curl 'https://www.bsr.de/abfuhrkalender_ajax.php?script=dynamic_search&step=1&q=germ'
            # -H 'Cookie: PHPSESSID=qtucu41smjm7cds15e695bss7osrcs5lrk1gmaco4j3a5uquq0f0; wt3_sid=%3B957773728431957;
            # wt_geid=pafDLBVIxBmgcvpffYJ5AkIF; wt_fweid=33fea4fb382763f39c51b3f4;
            # wt_feid=e7e07c85af0a2b503bb2e61fd8ffd3ac; wt_cdbeid=8c641c5c2fa74d82b14a4906fc58c6ff;
            # cookieconsent_status=dismiss; wt3_eid=%3B957773728431957%7C2154141380200060818%232154141441800946412'
            # -H 'Accept-Encoding: gzip, deflate, br'
            # -H 'Accept-Language: de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
            # -H 'User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)
            # Chrome/69.0.3497.100 Safari/537.36'
            # -H 'Accept: application/json, text/javascript, */*; q=0.01'
            # -H 'Referer: https://www.bsr.de/abfuhrkalender-20520.php'
            # -H 'X-Requested-With: XMLHttpRequest'
            # -H 'Connection: keep-alive'
            # --compressed

            url = 'https://www.bsr.de/abfuhrkalender_ajax.php?script=dynamic_search&step=1&q={}'.format(self.street)
            headers = {
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://www.bsr.de/abfuhrkalender-20520.php'
            }
            r = s.post(url, headers=headers)
            data = r.json()
            Domoticz.Debug('BSR: #2 working Streets:\t')
            relevantStreet = None

            if len(data) > 1:
                Domoticz.Log("Found more than one street - try to guess ...")
                for street in data:
                    # TODO wenn mehrere Strassen mit selber plz go deeper, check name
                    if(self.zip in street['value']):
                        relevantStreet = street
                        Domoticz.Debug("found street:\t{}".format(street))
                        break

            else:
                relevantStreet = data[0]

            if relevantStreet is None:
                raise Exception("Did not find a relevant street")
            # transform to bst like street
            # bsrParamRelvStreet = relevantStreet["value"].replace(" ", "%20")
            bsrParamRelvStreet = convertUrl(relevantStreet["value"])

            # bsrQueryRelvStreet = relevantStreet["value"].replace(",", "%2C").replace(" ", "+")
            bsrQueryRelvStreet = convert4Query(relevantStreet["value"])
            Domoticz.Debug("using for bsr street:\t'{}'\t'{}'".format(bsrParamRelvStreet, bsrQueryRelvStreet))
            # 2: get house number
            # curl 'https://www.bsr.de/abfuhrkalender_ajax.php?
            # script=dynamic_search&step=2&q=Germanenstr.,%2013156%20Berlin%20(Pankow)'
            # -H 'Cookie: PHPSESSID=qtucu41smjm7cds15e695bss7osrcs5lrk1gmaco4j3a5uquq0f0;
            # wt3_sid=%3B957773728431957; wt_geid=pafDLBVIxBmgcvpffYJ5AkIF;
            # wt_fweid=33fea4fb382763f39c51b3f4; wt_feid=e7e07c85af0a2b503bb2e61fd8ffd3ac;
            # wt_cdbeid=8c641c5c2fa74d82b14a4906fc58c6ff; cookieconsent_status=dismiss;
            # wt3_eid=%3B957773728431957%7C2154141380200060818%232154141441800946412'
            # -H 'Origin: https://www.bsr.de'
            # -H 'Accept-Encoding: gzip, deflate, br'
            # -H 'Accept-Language: de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
            # -H 'User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36
            # (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
            # -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8'
            # -H 'Accept: */*'
            # -H 'Referer: https://www.bsr.de/abfuhrkalender-20520.php'
            # -H 'X-Requested-With: XMLHttpRequest'
            # -H 'Connection: keep-alive'
            # --data 'step=2&q=Germanenstr.%2C+13156+Berlin+(Pankow)'
            # --compressed
            url = 'https://www.bsr.de/abfuhrkalender_ajax.php?'\
                'script=dynamic_search&step=2&q={}'.format(bsrParamRelvStreet)
            headers = {
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': '*/*',
                'Referer': 'https://www.bsr.de/abfuhrkalender-20520.php'
            }
            formdata = {
                'step': '2',
                'q': bsrQueryRelvStreet
            }
            r = s.post(url, headers=headers)
            json = r.json()
            Domoticz.Debug('BSR: #3 Numbers:\t')
            relevantNumber = None

            if len(json) > 1:
                Domoticz.Log("Found more than one number - try to guess ...")
                for k, v in json.items():
                    #    # for nr in json:
                    if(self.number == v['HouseNo']):
                        relevantNumber = v
                        Domoticz.Debug("found nr:\t{}".format(v))
            else:
                items = (list(json.values()))
                first = list(items)[0]
                # Domoticz.Error(first)
                relevantNumber = first

            if relevantNumber is None:
                raise Exception("Did not find a relevant number")

            # curl 'https://www.bsr.de/abfuhrkalender_ajax.php?script=dynamic_kalender_ajax'
            # -H 'Cookie: PHPSESSID=qtucu41smjm7cds15e695bss7osrcs5lrk1gmaco4j3a5uquq0f0;
            # wt3_sid=%3B957773728431957; wt_geid=pafDLBVIxBmgcvpffYJ5AkIF;
            # wt_fweid=33fea4fb382763f39c51b3f4; wt_feid=e7e07c85af0a2b503bb2e61fd8ffd3ac;
            # wt_cdbeid=8c641c5c2fa74d82b14a4906fc58c6ff; cookieconsent_status=dismiss;
            #  wt3_eid=%3B957773728431957%7C2154141380200060818%232154141851600765596'
            # -H 'Origin: https://www.bsr.de'
            # -H 'Accept-Encoding: gzip, deflate, br'
            # -H 'Accept-Language: de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
            # -H 'User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36
            # (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
            # -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8'
            # -H 'Accept: */*'
            # -H 'Referer: https://www.bsr.de/abfuhrkalender-20520.php'
            # -H 'X-Requested-With: XMLHttpRequest'
            # -H 'Connection: keep-alive'
            # --data 'abf_strasse=Germanenstr.&abf_hausnr=30&
            # tab_control=Liste&abf_config_weihnachtsbaeume=&
            # abf_config_restmuell=on&abf_config_biogut=on&
            # abf_config_wertstoffe=on&abf_config_laubtonne=on
            # &abf_selectmonth=11+2018&abf_datepicker=30.10.2018&listitems=7'
            # --compressed

            url = 'https://www.bsr.de/abfuhrkalender_ajax.php?script=dynamic_kalender_ajax'
            headers = {
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': '*/*',
                'Referer': 'https://www.bsr.de/abfuhrkalender-20520.php'
            }

            data = 'abf_strasse={}&'\
                'abf_hausnr={}&tab_control=Liste&'\
                'abf_config_weihnachtsbaeume=&'\
                'abf_config_restmuell=on&'\
                'abf_config_biogut=on&abf_config_wertstoffe=on&'\
                'abf_config_laubtonne=on&'\
                'abf_selectmonth=12+2018&'\
                'abf_datepicker=11.12.2018'\
                '&listitems=7'.format(
                    convert4Query(relevantNumber["Street"]),
                    relevantNumber["HouseNo"]
                )
            # Domoticz.Debug("data: {}".format(data))
            r = s.post(url, data=data, headers=headers)
            Domoticz.Debug('BSR: #4 Parse Data')

            soup = BeautifulSoup(r.content, 'html.parser')
            # Domoticz.Debug('BSR: #4.2 Date:\t scan html' )
            wertStoffDate = None
            restDate = None
            isFirst = True

            error = soup.find('li', {'class': 'abf_errormsg'})
            if(error is not None):
                Domoticz.Log("Could not load waste collection data. Raise exception")
                self.setError(error)
                raise Exception("Could not load data - verifiy settings")
            else:
                self.resetError()
            for tag in soup.find_all("li"):
                Domoticz.Log('BSR: #4.3\t {} - {} '.format(tag.time.get('datetime'), tag.img.get('alt')))
                if self.showHouseholdWaste is True:
                    scanAndParse(tag, self.restData)
                    self.checkForNearest(self.restData)
                if self.showRecycleWaste is True:
                    scanAndParse(tag, self.recycleData)
                    self.checkForNearest(self.recycleData)

                if self.showBioWaste is True:
                    scanAndParse(tag, self.bioData)
                    self.checkForNearest(self.bioData)

                # if we have all data, leave loop
                if (self.restData.isComplete() is True and
                    self.recycleData.isComplete() is True and
                        self.bioData.isComplete() is True):
                    break

            Domoticz.Log('BSR: #4.4\t gelber Sack {}\tHausmuell {} '
                         .format(self.recycleData.getDate(), self.restData.getDate()))

        except (Exception) as e:
            Domoticz.Error("Error: {} ".format(e))
            return
        self.lastUpdate = datetime.now()


#############################################################################
#                       Data specific functions                             #
#############################################################################


def calculateAlarmLevel(wasteDate):
    level = 1
    smallerTxt = ""
    if(wasteDate is not None):
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
            smallerTxt = '{} ({})'.format(smallerTxt, "Übermorgen")
        elif delta.days == 1:
            smallerTxt = '{} ({}!)'.format(smallerTxt, "Morgen")
        elif delta.days == 0:
            smallerTxt = '{} ({}!!!)'.format(smallerTxt, "Heute")
        else:
            smallerTxt = '{} ({} Tage)'.format(smallerTxt, delta.days)
    return [level, smallerTxt]


def scanAndParse(tag, wasteData: WasteData):
    if wasteData.isEmpty() and tag.find('span', {'class': wasteData.divClass}) is not None:
        Domoticz.Debug("found matching entry for {}" .format(wasteData.wasteType))
        result = ["", "", ""]
        try:
            result = parseBsrHtmlList(tag)
            if(result is not None):
                wasteData.wasteDate = result[0]
                wasteData.wasteType = result[1]
                wasteData.wasteHint = result[2]
            else:
                Domoticz.Debug("Result was empty?!")
        except Exception as e:
            Domoticz.Error("Could not parse content -> data {}\tresult {} ... exc: {} ".format(wasteData, result, e))
    return wasteData


def parseBsrHtmlList(tag):
    result = ["", "", ""]
    colName = tag.img.get('alt')
    Domoticz.Debug("colName {}".format(colName))
    colHint = tag.find('span', {'class': 'Hinweis'})
    if(colHint is not None):
        # Domoticz.Debug("Hinweis: {} ".format(hint['title']))
        colHint = colHint['title']
        colHint = colHint.replace('\n', '').replace('\r', '').replace('<br>', '')
        Domoticz.Debug("colHint {}".format(colHint))

    colDate = tag.time.get('datetime')
    Domoticz.Debug("colDate1 {}".format(colDate))
    colDate = getDate(colDate, '%Y-%m-%d')
    result = [colDate, colName, colHint]
    return result


def getDate(sDate: str, sFormat: str):
    """Parse string to date object.
    Trying it with datetime.strptime or time.strptime
    Helps walking around different domoticz behaviour between
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
    Helps walking around different domoticz behaviour between
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
    s = urllib.parse.quote(parameter)
    return s


def convert4Query(parameter: str):
    """replaces ',' with '%2C' and ' ' with '+' to work with bsr query parameter

    Arguments:
        parameter {str} -- the string to parse

    Returns:
        [type] -- str
    """
    s = urllib.parse.quote_plus(parameter)
    return s
    # return parameter.replace(",", "%2C").replace(" ", "+")
