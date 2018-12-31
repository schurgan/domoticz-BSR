"""
Bsr Waste Collection Date Reader Plugin

Author: Belze(2018)


Version:    1.0.0: Initial Version
            1.1.0: add support for xmas trees and more debug options
"""
"""


<plugin key="BsrWasteCollection"
name="BSR - Berlin Waste Collection" author="belze"
version="1.0.1" wikilink="" >
    <params>
        <param field="Mode1" label="Street" width="400px" required="true"
        default="Deeper Pfad"/>
        <param field="Mode2" label="Zipcode" width="50px" required="true"
        default="13503"/>
        <param field="Mode3" label="Number" width="50px" required="true"
        default="1"/>
        <param field="Mode4" label="Update every x hours" width="200px"
        required="true" default="24"/>

        <param field="Mode5" label="What Kind of collection should be listed" width="200px"
        title="here you can choose what to show">
            <options>
                <option label="only normal waste" value="only_waste"  selected="selected"/>
                <option label="waste and bio" value="waste_bio"/>
                <option label="waste and recycling" value="waste_recycling"   />
                <option label="waste, recycling and xmas" value="waste_recycling_xmas"   />
                <option label="waste, bio and recycling" value="waste_recycling_bio"   />
                <option label="waste, bio, recycling, xmas" value="waste_recycling_bio_xmas"   />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="False" />
                <option label="True full deatail" value="Debug_response"   />

            </options>
        </param>
        <param field="Mode7" label="Xmas Tree" width="75px">
            <options>
                <option label="True" value="True"/>
                <option label="False" value="False"  default="False" />
            </options>
        </param>
    </params>
</plugin>
"""
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from os import path
import sys
sys.path
sys.path.append('/volume1/@appstore/py3k/usr/local/lib/python3.5/site-packages')
sys.path.append('C:\\Program Files (x86)\\Python37-32\\Lib\\site-packages')

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

try:
    from bsr import Bsr
except Exception as e:
    pass


class BasePlugin:

    def __init__(self):
        self.debug = False
        self.error = False
        self.nextpoll = datetime.now()

        return

    def onStart(self):
        if 'Debug' in Parameters["Mode6"]:
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)

        Domoticz.Debug("onStart called")

        # check polling interval parameter
        try:
            temp = int(Parameters["Mode4"])
        except:
            Domoticz.Error("Invalid polling interval parameter")
        else:
            if temp < 6:
                temp = 6  # minimum polling interval
                Domoticz.Error("Specified polling interval too short: changed to 6 hours")
            elif temp > (24 * 5):
                temp = (24 * 5)  # maximum polling interval is 5 day
                Domoticz.Error("Specified polling interval too long: changed to 5 days")
            self.pollinterval = temp * 60 * 60
        Domoticz.Log("Using polling interval of {} seconds".format(str(self.pollinterval)))

        self.street = Parameters["Mode1"]
        self.zip = Parameters["Mode2"]
        self.nr = Parameters["Mode3"]

# TODO get settings for waste, recylce, bio

        self.showWaste = False
        self.showRecycle = False
        self.showBio = False
        if("bio" in Parameters["Mode5"]):
            self.showBio = True
        else:
            self.showBio = False

        if("waste" in Parameters["Mode5"]):
            self.showWaste = True
        else:
            self.showWaste = False

        if("recycling" in Parameters["Mode5"]):
            self.showRecycle = True
        else:
            self.showRecycle = False

        if("xmas" in Parameters["Mode5"]):
            self.showXmas = True
        else:
            self.showXmas = False

        if("response" in Parameters["Mode6"]):
            self.debugResponse = True
        else:
            self.debugResponse = False

        self.bsr = Bsr(self.street, self.zip, self.nr, self.showWaste,
                       self.showRecycle, self.showBio, showXmasWaste=self.showXmas, debugResponse=self.debugResponse)
        if self.debug is True:
            self.bsr.dumpBsrConfig()

        # Check if devices need to be created
        createDevices()

        # init with empty data
        updateDevice(1, 0, "No Data", "BSR")

    def onStop(self):
        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onHeartbeat(self):
        modulename = 'bs4'
        if modulename not in sys.modules:
            Domoticz.Log('{} not imported'.format(modulename))
        else:
            Domoticz.Log('{}: {}'.format(modulename, sys.modules[modulename]))

        myNow = datetime.now()
        if myNow >= self.nextpoll:
            Domoticz.Debug("----------------------------------------------------")
            self.nextpoll = myNow + timedelta(seconds=self.pollinterval)
            self.bsr.readBsrWasteCollection()

            alarmLevel = 0
            summary = 'No data'
            name = 'BSR'

            if(self.bsr.hasError is True):
                alarmLevel = 4
                summary = "msg: {}".format(self.bsr.errorMsg)
                name = '!BSR Error!'
                updateDevice(1, alarmLevel, summary, name)
            else:
                # check if update needed
                if self.bsr.needUpdate is True:
                    alarmLevel = self.bsr.getAlarmLevel()
                    summary = self.bsr.getSummary()
                    name = self.bsr.getDeviceName()
                    updateDevice(1, alarmLevel, summary, name)

            # check if
            # if self.bsr.needUpdate is True:
            #    updateDevice(1, self.bsr.getAlarmLevel(), self.bsr.getSummary(), self.bsr.getDeviceName())
            Domoticz.Debug("----------------------------------------------------")


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

#############################################################################
#                   common functions                     #
#############################################################################


# Generic helper functions


def DumpConfigToLog():
    '''just dumps the configuration to log.
    '''
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return


def parseIntValue(s):
    """Parse an int and return None if no int is given
     Arguments:
        s {str} -- string of int value
    Returns:
        int -- the value in int or None
    """
    try:
        return int(s)
    except:
        return None

#
# Parse a float and return None if no float is given
#


def parseFloatValue(s):

    try:
        return float(s)
    except:
        return None

#############################################################################
#                       Data specific functions                             #
#############################################################################


#############################################################################
#                       Device specific functions                           #
#############################################################################


def createDevices():
    '''
    this creates the alarm device for waste collection
    '''
    # create the mandatory child devices if not yet exist
    if 1 not in Devices:
        Domoticz.Device(Name="Müll", Unit=1, TypeName="Alert", Used=1).Create()
        Domoticz.Log("Devices[1] created.")


#
def updateDevice(Unit, alarmLevel, alarmData, name='', alwaysUpdate=False):
    '''update a device - means today or tomorrow, with given data.
    If there are changes and the device exists.
    Arguments:
        Unit {int} -- index of device, 1 = today, 2 = tomorrow
        highestLevel {[type]} -- the maximum warning level for that day, it is used to set the domoticz alarm level
        alarmData {[str]} -- data to show in that device, aka text

    Optional Arguments:
        name {str} -- optional: to set the name of that device, eg. mor info about  (default: {''})
        alwaysUpdate {bool} -- optional: to ignore current status/needs update (default: {False})
    '''

    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if (alarmData != Devices[Unit].sValue) or (int(alarmLevel) != Devices[Unit].nValue or alwaysUpdate is True):
            if(len(name) <= 0):
                Devices[Unit].Update(int(alarmLevel), alarmData)
            else:
                Devices[Unit].Update(int(alarmLevel), alarmData, Name=name)
            Domoticz.Log("BLZ: Updated to: {} value: {}".format(alarmData, alarmLevel))
        else:
            Domoticz.Log("BLZ: Remains Unchanged")
    else:
        Domoticz.Error("Devices[{}] is unknown. So we cannot update it.".format(Unit))
