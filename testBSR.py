#!/usr/bin/env python3
#
#   simple tests the meteo

from bsr import Bsr

# Berlijn
lat_be = 52.516667
lon_be = 13.416667


def createTestUmalute():
    print("#################################")
    print("Test Umlaute")
    y = Bsr("Am Schülerheim", "14195", "4")
    return y


def creatTestMultiple():
    print("#################################")
    print("Test Multiple")
    y = Bsr("Am Falkenberg", "12524", "1")
    # y = Bsr("de", "Am Falkenberg am Wasserwerk", "12524", "1")
    return y


def creatTestBio():
    print("#################################")
    print("Test Bio")
    y = Bsr("Barfusstr.", "13349", "1", showRecycleWaste=False)
    return y


def creatTestLikePlugin():
            # test like plugin default
    print("#################################")
    print("Test like plugin")
    # kein wertstoffe
    y = Bsr("Deeper Pfad", "13503", "1",
            showHouseholdWaste=True,
            showRecycleWaste=False, showBioWaste=False)
    return y


def creatTestXmasLikePlugin():
            # test like plugin default
    print("#################################")
    print("Test like plugin")
    # kein wertstoffe
    y = Bsr("Deeper Pfad", "13503", "1",
            showHouseholdWaste=True,
            showRecycleWaste=False, showBioWaste=False, showXmasWaste=True)
    return y


def runTest(bsr: Bsr):
    bsr.dumpBsrConfig()
    bsr.readBsrWasteCollection()
   # bsr.dumpBsrStatus()
    bsr.dumpBsrStatus()
    print("summary: {}".format(bsr.getSummary()))
    print("date: {} \nlevel:{} \ntxt: {} \nname: {}".format(bsr.getNearestDate(),
                                                            bsr.getAlarmLevel(), bsr.getAlarmText(),
                                                            bsr.getDeviceName()))


# y = createTestUmalute()
# runTest(y)

# y = creatTestMultiple()
# runTest(y)

# b = creatTestBio()
# runTest(b)

# d = creatTestLikePlugin()
# runTest(d)

e = creatTestXmasLikePlugin()
runTest(e)
