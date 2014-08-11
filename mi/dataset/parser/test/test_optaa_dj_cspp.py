#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_optaa_dj_cspp
@file marine-integrations/mi/dataset/parser/test/test_optaa_dj_cspp.py
@author Joe Padula
@brief Test code for a optaa_dj_cspp data parser
"""

import os
import yaml
import numpy

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import RecoverableSampleException

from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.cspp_base import \
    StateKey, \
    METADATA_PARTICLE_CLASS_KEY, \
    DATA_PARTICLE_CLASS_KEY

from mi.dataset.parser.optaa_dj_cspp import \
    OptaaDjCsppParser, \
    OptaaDjCsppInstrumentTelemeteredDataParticle, \
    OptaaDjCsppMetadataTelemeteredDataParticle, \
    OptaaDjCsppInstrumentRecoveredDataParticle, \
    OptaaDjCsppMetadataRecoveredDataParticle

from mi.dataset.driver.optaa_dj.cspp.driver import DataTypeKey
# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'optaa_dj', 'cspp', 'resource')

RECOVERED_SAMPLE_DATA = '11079364_ACS_ACS.txt'
TELEMETERED_SAMPLE_DATA = '11079364_ACD_ACS.txt'


@attr('UNIT', group='mi')
class OptaaDjCsppParserUnitTestCase(ParserUnitTestCase):
    """
    optaa_dj_cspp Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value.append(exception)
        self.count += 1

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: OptaaDjCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: OptaaDjCsppInstrumentTelemeteredDataParticle,
                }
            },
            DataTypeKey.OPTAA_DJ_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: OptaaDjCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: OptaaDjCsppInstrumentRecoveredDataParticle,
                }
            },
        }
        # Define test data particles and their associated timestamps which will be
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = []
        self.count = 0

    def particle_to_yml(self, particles, filename, mode='w'):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml fids here.
        """
        # open write append, if you want to start from scratch manually delete this fid
        fid = open(os.path.join(RESOURCE_PATH, filename), mode)

        fid.write('header:\n')
        fid.write(" particle_object: 'MULTIPLE'\n")
        fid.write(" particle_type: 'MULTIPLE'\n")
        fid.write('data:\n')

        for i in range(0, len(particles)):
            particle_dict = particles[i].generate_dict()

            fid.write(' - _index: %d\n' % (i+1))

            fid.write('   particle_object: %s\n' % particles[i].__class__.__name__)
            fid.write('   particle_type: %s\n' % particle_dict.get('stream_name'))
            fid.write('   internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))

            for val in particle_dict.get('values'):
                if isinstance(val.get('value'), float):
                    fid.write('   %s: %16.16f\n' % (val.get('value_id'), val.get('value')))
                elif isinstance(val.get('value'), str):
                    fid.write("   %s: '%s'\n" % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('   %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def get_dict_from_yml(self, filename):
        """
        This utility routine loads the contents of a yml file
        into a dictionary
        """

        fid = open(os.path.join(RESOURCE_PATH, filename), 'r')
        result = yaml.load(fid)
        fid.close()

        return result

    def create_yml(self):
        """
        This utility creates a yml file
        """

        fid = open(os.path.join(RESOURCE_PATH, TELEMETERED_SAMPLE_DATA), 'r')

        stream_handle = fid
        parser = OptaaDjCsppParser(self.config.get(DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED),
                                   None, stream_handle,
                                   self.state_callback, self.pub_callback,
                                   self.exception_callback)

        particles = parser.get_records(20)

        self.particle_to_yml(particles, '11079364_ACD_ACS_telem.yml')
        fid.close()

    def assert_result(self, test, particle):
        """
        Suite of tests to run against each returned particle and expected
        results of the same. The test parameter should be a dictionary
        that contains the keys to be tested in the particle
        the 'internal_timestamp' and 'position' keys are
        treated differently than others but can be verified if supplied
        """

        particle_dict = particle.generate_dict()

        # for efficiency turn the particle values list of dictionaries into a dictionary
        particle_values = {}
        for param in particle_dict.get('values'):
            particle_values[param['value_id']] = param['value']
            # log.debug('### building building particle values ###')
            # log.debug('value_id = %s', param['value_id'])
            # log.debug('value = %s', param['value'])

        # compare each key in the test to the data in the particle
        for key in test:
            test_data = test[key]

            # get the correct data to compare to the test
            if key == 'internal_timestamp':
                particle_data = particle.get_value('internal_timestamp')
                #the timestamp is in the header part of the particle
            elif key == 'position':
                particle_data = self.state_callback_value['position']
                #position corresponds to the position in the file
            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            # log.debug('*** assert result: test data key = %s', key)
            # log.debug('*** assert result: test data val = %s', test_data)
            # log.debug('*** assert result: part data val = %s', particle_data)

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                if isinstance(test_data, float):

                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(test_data - particle_data) <= 1e-5
                    # log.debug('*** assert result: compare = %s', compare)
                    self.assertTrue(compare)
                else:
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(test_data, particle_data)

    def test_simple(self):
        """
        Read test data and pull out 20 data particles.
        Assert that the results are those we expected.
        """
        log.debug('test_simple')
        file_path = os.path.join(RESOURCE_PATH, '11079364_ACS_ACS_one_data_record.txt')
        stream_handle = open(file_path, 'r')
        # data = stream_handle.read(1024)
        # log.debug("Data %s", data)

        # Note: since the recovered and telemetered parser and particles are common
        # to each other, testing one is sufficient, will be completely tested
        # in driver tests
        log.debug('creating parser')

        parser = OptaaDjCsppParser(self.config.get(DataTypeKey.OPTAA_DJ_CSPP_RECOVERED),
                                   None, stream_handle,
                                   self.state_callback, self.pub_callback,
                                   self.exception_callback)

        log.debug('parser: %s', parser)
        #particles = parser.get_records(20)
        particles = parser.get_records(1)
        log.debug('particle: %s', particles)
        #
        # log.debug("*** test_simple Num particles %s", len(particles))
        #
        # # load a dictionary from the yml file
        # test_data = self.get_dict_from_yml('11079364_PPB_CTD_recov.yml')
        #
        # # check all the values against expected results.
        #
        # for i in range(len(particles)):
        #
        #     self.assert_result(test_data['data'][i], particles[i])
        #
        # stream_handle.close()

    def test_get_many(self):
	"""
	Read test data and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
        pass

    def test_long_stream(self):
        """
        Test a long stream 
        """
        pass

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        pass

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        pass

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        pass
