import unittest
import sys
import logging
import codecs


sys.path.insert(0, "..")
from bsr.bsr import Bsr
import configparser

CONFIG_SECTION_MY = "address_my"
CONFIG_SECTION_STANDARD = "address_standard"
CONFIG_SECTION_BIO = "address_bio"
CONFIG_SECTION_MULTI = "address_multi"
CONFIG_SECTION_UMLAUT = "address_umlaut"

# set up logger
logger = logging.getLogger()
logger.level = logging.DEBUG


class Test_bsr(unittest.TestCase):
    def setUp(self):
        # work around logger
        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)
        logging.getLogger().info("# set up test for bsr")

    def tearDown(self):
        logging.getLogger().info("# tear down: test for bsr")
        if self.bsr:
            self.bsr.reset()
            self.bsr = None

        # remove logger
        logger.removeHandler(self.stream_handler)

    def test_myAddress(self):
        """
        takes address from **my** config and tests it
        """
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/my_config.ini", encoding="utf-8"))

        self.bsr = self.readAndCreate(config, CONFIG_SECTION_MY)
        self.doWork(self.bsr)

    def test_Standard(self):
        """
        takes standrad address from common config and tests it
        """
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/common_config.ini", encoding="utf-8"))
        self.bsr = self.readAndCreate(
            aConfig=config,
            aSection=CONFIG_SECTION_STANDARD,
            showRecycleWaste=True,
            showXmasWaste=True,
        )
        self.doWork(self.bsr)

    def test_Bio(self):
        """
        takes address from common config and tests it for bio waste collection.
        should run without issues, even if no plastic/recycling is there
        """
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/common_config.ini", encoding="utf-8"))
        self.bsr = self.readAndCreate(config, CONFIG_SECTION_BIO, showBioWaste=True)
        self.doWork(self.bsr)

    def test_Umlaut(self):
        """
        takes address from common config and tests if it works also with Umlaute
        """
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/common_config.ini", encoding="utf-8"))
        self.bsr = self.readAndCreate(config, CONFIG_SECTION_UMLAUT)
        self.doWork(self.bsr)

    def test_Multi(self):
        """
        takes address from common config and tests if address result in multiple
        entries
        """
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/common_config.ini", encoding="utf-8"))
        self.bsr = self.readAndCreate(config, CONFIG_SECTION_MULTI)
        self.doWork(self.bsr)

    def readAndCreate(
        self,
        aConfig,
        aSection,
        showHouseholdWaste: bool = True,
        showRecycleWaste: bool = True,
        showBioWaste: bool = True,
        showXmasWaste: bool = False,
        debugResponse: bool = False,
    ):
        """creates a bsr object based on config

        Args:
            aConfig ([type]): [configuration holding the address]

        Returns:
            [Bsr]: [bsr object]
        """
        self.assertTrue(
            aConfig.has_section(aSection),
            "we need this set up:  " + aSection,
        )
        str = aConfig.get(aSection, "street")
        zip = aConfig.get(aSection, "zip")
        nr = aConfig.get(aSection, "nr")

        aBsr = Bsr(
            street=str,
            zipCode=zip,
            houseNumber=nr,
        )
        return aBsr

    def doWork(self, aBsr: Bsr):
        """quickly reads content from internet

        Args:
            aBsr (Bsr): the object to test
        """
        self.assertIsNotNone(
            aBsr, "We do not an object of bsr, otherwise no tests are possible"
        )
        aBsr.dumpConfig()
        self.assertIsNone(aBsr.getNearestDate(), "obj is fresh, so should be empty")
        self.assertFalse(aBsr.hasErrorX(), "obj is fresh, so should stay with null")
        aBsr.readBsrWasteCollection()
        aBsr.dumpStatus()
        self.assertIsNotNone(aBsr.getSummary())
        self.assertIsNotNone(aBsr.getNearestDate())
        self.assertIsNotNone(aBsr.getAlarmLevel())
        self.assertTrue(aBsr.needsUpdate())
        logging.getLogger().info("summary: {}".format(aBsr.getSummary()))
        logging.getLogger().info(
            "date: {} \nlevel:{} \ntxt: {} \nname: {}".format(
                aBsr.getNearestDate(),
                aBsr.getAlarmLevel(),
                aBsr.getAlarmText(),
                aBsr.getDeviceName(),
            )
        )


if "__main__" == __name__:
    unittest.main()
