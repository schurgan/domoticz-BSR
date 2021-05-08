import unittest
import sys
import logging
import codecs


sys.path.insert(0, "..")
from blz.blzHelperInterface import BlzHelperInterface
from plugin import BasePlugin

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


class Test_plugin(unittest.TestCase):
    def setUp(self):
        # work around logger
        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)
        logging.getLogger().info("# set up test for bsr")
        self.plugin = BasePlugin()  #plugin()
        
        config = configparser.ConfigParser()
        config.read_file(codecs.open(r"./test/my_config.ini", encoding="utf-8"))
        self.bsr = self.readAndCreate(config, CONFIG_SECTION_MY)

        self.plugin.bsr = self.bsr  

    def tearDown(self):
        logging.getLogger().info("# tear down: test for bsr")
        if self.plugin:
            self.plugin = None

        # remove logger
        logger.removeHandler(self.stream_handler)

    def test_onStart(self):
        logging.getLogger().info("#fake start of plugin")
        #TODO call: 
        self.plugin.onStart()

    def test_onHeartbeat(self):
        logging.getLogger().info("#fake heart beat")
        #TODO call: 
        self.plugin.onHeartbeat()

    def test_onStop(self):
        logging.getLogger().info("#fake stop")
        #TODO call: 
        self.plugin.onStop()


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

if "__main__" == __name__:
    unittest.main()
