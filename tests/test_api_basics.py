
from datetime import datetime, timedelta
import pytest
import os.path

try:
    from urlparse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse
    from cgi import parse_qs

from tests import TESTABLE_API_VERSIONS, XML_TEST_DIR
from tests.utils import convert_camel_case, extract_operations_from_wsdl

from amazonproduct.api import API
from amazonproduct.errors import UnknownLocale, TooManyRequests, InvalidClientTokenId


class TestAPILocales (object):

    """
    Testing initialising API with different locales.
    """

    ACCESS_KEY = SECRET_KEY = ''

    def test_fails_for_invalid_locale(self):
        pytest.raises(UnknownLocale, API, self.ACCESS_KEY,
                self.SECRET_KEY, locale='XX')


class TestAPICallsWithOptionalParameters (object):

    """
    Tests that optional parameters (like AssociateTag) end up in URL.
    """

    def test_associate_tag_is_written_to_url(self):
        tag = 'ABC12345'
        api = API('XXX', 'XXX', 'de', associate_tag=tag)
        url = api._build_url(Operation='ItemSearch', SearchIndex='Books')

        qs = parse_qs(urlparse(url)[4])
        assert qs['AssociateTag'][0] == tag


class TestAPIInitialisation (object):

    """
    Test all the different ways an API instance can be instantiated.
    """

    def test_init_with_parameters(self):
        api = API('ACCESS_KEY', 'SECRET_KEY', 'de', 'associate-tag')

    def test_init_with_config_file(self, configfiles):
        configfiles.add_file("""
        [Credentials]
        aws_access_key_id = ABCDEFGH12345
        aws_secret_access_key = abcdegf43
        aws_product_locale = de""") 
        api = API()

    def test_init_with_config_file(self, configfiles):
        configfiles.add_file("""
        [Credentials]
        aws_access_key_id = ABCDEFGH12345
        aws_secret_access_key = abcdegf43
        aws_product_locale = de""") 
        api = API()

    def test_init_with_config_file_and_parameters(self, configfiles):
        configfiles.add_file("""
        [Credentials]
        aws_access_key_id = ABCDEFGH12345
        aws_secret_access_key = abcdegf43""") 
        API(locale='de')

    def test_init_with_incomplete_config_file(self, configfiles):
        configfiles.add_file("""
        [Credentials]
        aws_access_key_id = ABCDEFGH12345
        aws_secret_access_key = abcdegf43""") 
        pytest.raises(UnknownLocale, API)


def pytest_generate_tests(metafunc):
    # called once per each test function
    if 'api' in metafunc.funcargnames and 'operation' in metafunc.funcargnames:
        for version in metafunc.config.option.versions or TESTABLE_API_VERSIONS:
            wsdl = os.path.join(XML_TEST_DIR, version, 
                                'AWSECommerceService.wsdl')
            if not os.path.exists(wsdl):
                operations = ['???']
            else:
                operations = extract_operations_from_wsdl(wsdl)
            for operation in operations:
                metafunc.addcall(
                    id='%s/%s' % (version, operation),
                    param={'operation' : operation, 'version' : version,
                           'wsdl_path' : wsdl})

def pytest_funcarg__api(request):
    server = request.getfuncargvalue('server')
    api = API('XXX', 'XXX', 'uk') # locale does not matter here!
    api.host = ['%s:%s' % server.server_address for _ in range(2)]
    if hasattr(request, 'param'): # for tests generated by pytest_generate_tests
        api.VERSION = request.param['version']
        api.REQUESTS_PER_SECOND = 10000 # just for here!
    return api

def pytest_funcarg__operation(request):
    if request.param['operation'] == '???':
        raise pytest.skip('No WSDL found at %s!' % request.param['wsdl_path'])
    return request.param['operation']

class TestAPICalls (object):

    """
    Test API calls with ``TestServer`` instance.
    """

    def test_fails_for_wrong_aws_key(self, api, server):
        xml = open(os.path.join(XML_TEST_DIR,
            'APICalls-fails-for-wrong-aws-key.xml')).read()
        server.serve_content(xml, 403)
        pytest.raises(InvalidClientTokenId, api.item_lookup, '9780747532743')

    def test_fails_for_too_many_requests(self, api, server):
        xml = open(os.path.join(XML_TEST_DIR,
            'APICalls-fails-for-too-many-requests.xml')).read()
        server.serve_content(xml, 503)
        pytest.raises(TooManyRequests, api.item_lookup, '9780747532743',
            IdType='ISBN', SearchIndex='All', ResponseGroup='???')

    @pytest.mark.slowtest
    def test_call_throtteling(self, api, server):
        api.REQUESTS_PER_SECOND = 1
        server.code = 200
        start = datetime.now()
        n = 3
        for i in range(n):
            api._fetch(server.url)
        stop = datetime.now()
        throttle = timedelta(seconds=1)/api.REQUESTS_PER_SECOND
        assert (stop-start) >= (n-1)*throttle

def test_API_coverage(api, operation):
    """
    Tests if API class supports all operations which are in the official WSDL
    from Amazon.
    """
    # a few operations are not yet implemented!
    notyetimpltd = 'SellerLookup SellerListingLookup SellerListingSearch'
    if operation in notyetimpltd.split():
        pytest.xfail('Not yet fully implemented!')

    attr = convert_camel_case(operation)
    assert hasattr(api, attr), 'API does not support %s!' % operation

