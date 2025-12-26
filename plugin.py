# plugin for displaying waste collections date from berlins waste company
#
# Author: belze
#
"""
Bsr Waste Collection Date Reader Plugin

Author: Belze(2021)


Version:    1.0.0: Initial Version
            1.1.0: add support for xmas trees and more debug options
            1.1.1: now xmas tree collection date is only shown in December and January
            1.1.2: for device name: removed content in '(foo)' from waste type, to keep it short
            1.1.3: if there is an error, ignore polling time and try with next heart beat
            1.1.4: update also if we have a day change on hearbeat, so we will get correct device name
            1.1.5: small fix to ignore dates older then today entries for waste disposal,
                   eg. xmas tree always returned full list.
            1.1.6: new debug option to turn on fast reload from service, polltime is handled as minutes
            1.1.7: bugfix, forgot to clear data storage before reading them from webservice
            2.0.0: rebuild project structure and parameters
            3.0.0: changed to new webpage form BSR
            3.0.1: 

<plugin key="BsrWasteCollection"
name="BSR - Berlin Waste Collection" author="belze/schurgan/ChatGPT"
version="3.0.0" wikilink="" externallink="https://github.com/schurgan/domoticz-BSR" >
    <description>
        <h2>BSR - Berlin Waste Collection Plugin</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>shows next dates of selected waste collections</li>
            <li>using alarm device to signal how close the next collection is</li>
            <li>if problems occur - device shows it</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>BSR - Alarm device to show data</li>
        </ul>
        <h3>Hint</h3>
        Best is visit first -><a href="https://www.bsr.de/abfuhrkalender-20520.php">
        BSR_</a>  to verify your address.
    </description>

    <params>
        <param field="Mode1" label="Street" width="400px" required="true"
        default="Deeper Pfad"/>
        <param field="Mode2" label="Zipcode" width="50px" required="true"
        default="13503"/>
        <param field="Mode3" label="Number" width="50px" required="true"
        default="1"/>
        <param field="Mode4" label="Update every x hours" width="200px"
        required="true" default="6"/>

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
                <option label="True fast full deatail" value="Debug_response_fast"   />
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
import traceback

sys.path
try:
    import Domoticz  # pylint: disable=import-error # nopep8
except ImportError:
    from blz import fakeDomoticz as Domoticz
    from blz.fakeDomoticz import Parameters
    from blz.fakeDomoticz import Devices
    from blz.fakeDomoticz import Images

try:
    from bsr.bsr import Bsr
except Exception as e:
    import traceback
    Domoticz.Error("could not load bsr lib: {}".format(e))
    Domoticz.Error("IMPORT TRACEBACK:\n{}".format(traceback.format_exc()))
    raise


POLL_THRESHOLD_MIN_HOURS =  6 #:minimum time in hours to fetch new data
POLL_THRESHOLD_MAX_HOURS =  24 * 5  #:max time in hours to fetch new data aka 5 days
DEFAULT_POLL_INTERVAL_HOURS = POLL_THRESHOLD_MIN_HOURS #:standard to use if wrong, missing or buggy
class BasePlugin:
    def __init__(self):
        self.debug = False
        self.debugFast = False
        self.error = False
        self.nextpoll = datetime.now()
        self.errorCounter = 0
        # init with next poll to avoid NONE validation
        self.lastUpdate = self.nextpoll
        self.pollinterval = DEFAULT_POLL_INTERVAL_HOURS
        return

    def onStart(self):
        if "Debug" in Parameters["Mode6"]:
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)

        Domoticz.Debug("onStart called")
                # Beim Plugin-Restart bleibt bsr.bsr im Speicher -> neu laden erzwingen
        import sys
        import importlib
        if "bsr.bsr" in sys.modules:
            Domoticz.Log("BSR: reloading module bsr.bsr (plugin restart)")
            importlib.reload(sys.modules["bsr.bsr"])

        self.street = Parameters["Mode1"]
        self.zip = Parameters["Mode2"]
        self.nr = Parameters["Mode3"]

        # TODO get settings for waste, recycle, bio

        self.showWaste = False
        self.showRecycle = False
        self.showBio = False
        if "bio" in Parameters["Mode5"]:
            self.showBio = True
        else:
            self.showBio = False

        if "waste" in Parameters["Mode5"]:
            self.showWaste = True
        else:
            self.showWaste = False

        if "recycling" in Parameters["Mode5"]:
            self.showRecycle = True
        else:
            self.showRecycle = False

        if "xmas" in Parameters["Mode5"]:
            self.showXmas = True
        else:
            self.showXmas = False

        if "response" in Parameters["Mode6"]:
            self.debugResponse = True
        else:
            self.debugResponse = False

        if "fast" in Parameters["Mode6"]:
            self.debugFast = True
        else:
            self.debugFast = False

        # now lets set poll time after we do have all debug options
        # check polling interval parameter
        try:
            temp = int(Parameters["Mode4"])
        except:
            Domoticz.Error("Invalid polling interval parameter")
        else:
            if self.debugFast is True:
                Domoticz.Debug(
                    "Fast debug is turned on, so handle poll time as minutes!"
                )
                if temp < 1 and temp > 180:
                    temp = 5
                    Domoticz.Error(
                        "Even on Debug per minute update time should between 1 and 180"
                    )
                self.pollinterval = temp * 60
            else:
                if temp < POLL_THRESHOLD_MIN_HOURS:
                    temp = POLL_THRESHOLD_MIN_HOURS  # minimum polling interval
                    Domoticz.Error(
                        "Specified polling interval too short: changed to 6 hours"
                    )
                elif temp > POLL_THRESHOLD_MAX_HOURS:
                    temp = POLL_THRESHOLD_MAX_HOURS
                    Domoticz.Error(
                        "Specified polling interval too long: changed to 5 days"
                    )
                self.pollinterval = temp * 60 * 60
        Domoticz.Log(
            "Using polling interval of {} seconds".format(str(self.pollinterval))
        )
        
        from bsr.bsr import Bsr

        self.bsr = Bsr(
            self.street,
            self.zip,
            self.nr,
            self.showWaste,
            self.showRecycle,
            self.showBio,
            showXmasWaste=self.showXmas,
            debugResponse=self.debugResponse,
        )
        if self.debug is True:
            self.bsr.dumpConfig()

        # Check if devices need to be created
        createDevices()

        # init with empty data
        updateDevice(1, 0, "No Data", "BSR")

    def onStop(self):
        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "onCommand called for Unit "
            + str(Unit)
            + ": Parameter '"
            + str(Command)
            + "', Level: "
            + str(Level)
        )

    def onHeartbeat(self):
                # Heartbeat kann kommen, bevor onStart() fertig ist (Plugin-Restart)
        if not hasattr(self, "bsr") or self.bsr is None:
            Domoticz.Log("BSR: bsr not initialized yet -> skip heartbeat")
            return
        modulename = "bs4"
        if modulename not in sys.modules:
            Domoticz.Log("{} not imported".format(modulename))
        else:
            Domoticz.Debug("{}: {}".format(modulename, sys.modules[modulename]))

        myNow = datetime.now()
        # Domoticz.Debug("now: {} last: {}".format(myNow.day, self.lastUpdate.day))
        if myNow >= self.nextpoll or (myNow.day != self.lastUpdate.day):
            Domoticz.Debug("----------------------------------------------------")
            try:
                self.bsr.readBsrWasteCollection()
            except Exception:
                Domoticz.Error("BSR: Exception:\n{}".format(traceback.format_exc()))
                raise

            alarmLevel = 0
            summary = "No data"
            name = "BSR"

            if self.bsr.hasErrorX() is True:
                self.errorCounter += 1
                alarmLevel = 4
                summary = "msg: {}".format(self.bsr.getErrorMsg())
                name = "!BSR Error!"
                updateDevice(1, alarmLevel, summary, name)

                if self.errorCounter % 10:
                    Domoticz.Log(
                        "got {} times an error, wait 5 min before try again".format(
                            self.errorCounter
                        )
                    )
                    self.nextpoll = myNow + timedelta(minutes=5)

            else:
                # no error, reset counter
                self.errorCounter = 0
                # check if update needed
                if self.bsr.needsUpdate() is True:
                    alarmLevel = self.bsr.getAlarmLevel()
                    summary = self.bsr.getSummary()
                    name = self.bsr.getDeviceName()
                    # TODO as we change name but updateDevice is not checking this, we say alwaysUpdate
                    updateDevice(1, alarmLevel, summary, name, True)
                    self.lastUpdate = myNow
                # only on success set next poll time, so on error, we run it next heartbeat
                self.nextpoll = myNow + timedelta(seconds=self.pollinterval)

            # check if
            # if self.bsr.needUpdate is True:
            #    updateDevice(1, self.bsr.getAlarmLevel(), self.bsr.getSummary(), self.bsr.getDeviceName())
            Domoticz.Debug("next poll: {}".format(self.nextpoll))
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
    """just dumps the configuration to log."""
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
    """
    this creates the alarm device for waste collection
    """
    # create the mandatory child devices if not yet exist
    if 1 not in Devices:
        Domoticz.Device(Name="Müll", Unit=1, TypeName="Alert", Used=1).Create()
        Domoticz.Log("Devices[1] created.")


#
def updateDevice(Unit, alarmLevel, alarmData, name="", alwaysUpdate=False):
    """update a device - means today or tomorrow, with given data.
    If there are changes and the device exists.
    Arguments:
        Unit {int} -- index of device, 1 = today, 2 = tomorrow
        highestLevel {[type]} -- the maximum warning level for that day, it is used to set the domoticz alarm level
        alarmData {[str]} -- data to show in that device, aka text

    Optional Arguments:
        name {str} -- optional: to set the name of that device, eg. mor info about  (default: {''})
        alwaysUpdate {bool} -- optional: to ignore current status/needs update (default: {False})
    """

    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if (alarmData != Devices[Unit].sValue) or (
            int(alarmLevel) != Devices[Unit].nValue or alwaysUpdate is True
        ):
            if len(name) <= 0:
                Devices[Unit].Update(int(alarmLevel), alarmData)
            else:
                Devices[Unit].Update(int(alarmLevel), alarmData, Name=name)
            Domoticz.Log("BLZ: Updated to: {} value: {}".format(alarmData, alarmLevel))
        else:
            Domoticz.Log("BLZ: Remains Unchanged")
    else:
        Domoticz.Error("Devices[{}] is unknown. So we cannot update it.".format(Unit))
