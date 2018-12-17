#!/usr/bin/env python3
#
#   simple tests the meteo

from bsr import Bsr

# Berlijn
lat_be = 52.516667
lon_be = 13.416667


print("#################################")
# test umlaute and spaces
y = Bsr("Am Schülerheim", "14195", "4")
y.readBsrWasteCollection()
y.dumpBsrStatus()
print("#################################")
# test multiple streets for zip code
y = Bsr("Am Falkenberg", "12524", "1")
# y = Bsr("de", "Am Falkenberg am Wasserwerk", "12524", "1")

# test bio
print("#################################")
# kein wertstoffe
y = Bsr("Barfusstr.", "13349", "1", showRecycleWaste=False)
y.dumpBsrConfig()
y.readBsrWasteCollection()
y.dumpBsrStatus()
print("date: {} level:{} txt: {} name: {}".format(y.getNearestDate(),
                                                  y.getAlarmLevel(), y.getAlarmText(),
                                                  y.getDeviceName()))

# test like plugin default
print("#################################")
# kein wertstoffe
y = Bsr("Deeper Pfad", "13503", "1",
        showHouseholdWaste=True,
        showRecycleWaste=False, showBioWaste=False)
y.dumpBsrConfig()
y.readBsrWasteCollection()
y.dumpBsrStatus()
print("date: {} level:{} txt: {} name: {}".format(y.getNearestDate(),
                                                  y.getAlarmLevel(), y.getAlarmText(),
                                                  y.getDeviceName()))

# test bio, rest, recycling
print("#################################")
# kein wertstoffe
y = Bsr("Germanenstr", "13156", "21",
        showHouseholdWaste=True,
        showRecycleWaste=True, showBioWaste=True)
y.dumpBsrConfig()
y.readBsrWasteCollection()
y.dumpBsrStatus()
# print("date: {} level:{} txt: {} name: {}".format(y.getNearestDate(),
#                                                  y.getAlarmLevel(), y.getAlarmText(),
#                                                  y.getDeviceName()))
# y.readBsrWasteCollection()
print("summary: {}".format(y.getSummary()))
