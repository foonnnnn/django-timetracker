#pylint: disable-all

'''The test suite for the Timetracking application.

This module performs automated tests so that we can formally verify
that our application works.

Generally, when adding new functionality you will want to write tests
before it and then write your new feature whilst checking the tests.'''
import datetime
import simplejson
import random
import functools
import time
from unittest import skipUnless

from django.db import IntegrityError
from django.test import TestCase, LiveServerTestCase
from django.http import HttpResponse, Http404

from timetracker.tracker.models import (Tbluser,
                            TrackingEntry,
                            Tblauthorization)

from timetracker.middleware.exception_handler import UnreadablePostErrorMiddleware
from django.http import UnreadablePostError

from timetracker.utils.calendar_utils import (validate_time, parse_time,
                                              delete_user, useredit,
                                              mass_holidays, ajax_delete_entry,
                                              gen_calendar, ajax_change_entry,
                                              ajax_error)
from timetracker.utils.datemaps import pad, float_to_time, generate_select, ABSENT_CHOICES
from timetracker.utils.error_codes import DUPLICATE_ENTRY

try:
    from selenium.webdriver.firefox.webdriver import WebDriver
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def create_users(cls):
    '''we create users which will be linked to test how the automatic,
    retrieval of the links works'''

    cls.linked_super_user = Tbluser.objects.create(
        user_id="test.super@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="SUPER",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )


    cls.linked_manager = Tbluser.objects.create(
        user_id="test.manager@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="ADMIN",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    cls.linked_user = Tbluser.objects.create(
        user_id="test.user@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="RUSER",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    users = [
    Tbluser.objects.create(
            user_id="test.user%d@test.com" % userid,
            firstname="test",
            lastname="case",
            password="password",
            user_type="RUSER",
            market="BG",
            process="AP",
            start_date=datetime.datetime.today(),
            breaklength="00:15:00",
            shiftlength="07:45:00",
            job_code="00F20G",
            holiday_balance=20
            )
    for userid in range(5)]
    users.append(
        Tbluser.objects.create(
            user_id="test.user7@test.com",
            firstname="test",
            lastname="case",
            password="password",
            user_type="RUSER",
            market="BG",
            process="AO",
            start_date=datetime.datetime.today(),
            breaklength="00:15:00",
            shiftlength="07:45:00",
            job_code="00F20G",
            holiday_balance=20
            )
        )

    cls.linked_teamlead = Tbluser.objects.create(
        user_id="test.teamlead@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="TEAML",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    # create the links for the linked users
    cls.authorization = Tblauthorization.objects.create(admin=cls.linked_manager)
    cls.authorization.save()
    cls.authorization.users.add(cls.linked_user, cls.linked_teamlead)
    [cls.authorization.users.add(user) for user in users]
    cls.authorization.save()

    cls.supauthorization = Tblauthorization.objects.create(admin=cls.linked_super_user)
    cls.supauthorization.users.add(cls.linked_manager, cls.linked_teamlead, cls.linked_user)
    cls.supauthorization.save()

    cls.unlinked_super_user = Tbluser.objects.create(
        user_id="test.unlinkedsuper@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="SUPER",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    cls.unlinked_manager = Tbluser.objects.create(
        user_id="test.unlinkedmanager@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="ADMIN",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    cls.unlinked_user = Tbluser.objects.create(
        user_id="test.unlinkeduser@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="RUSER",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

    cls.unlinked_teamlead = Tbluser.objects.create(
        user_id="test.unlinkedteamlead@test.com",
        firstname="test",
        lastname="case",
        password="password",
        user_type="TEAML",
        market="BG",
        process="AP",
        start_date=datetime.datetime.today(),
        breaklength="00:15:00",
        shiftlength="07:45:00",
        job_code="00F20G",
        holiday_balance=20
        )

def delete_users(cls):
    '''Deletes all the users on a Tbluser instance.'''
    [user.delete() for user in Tbluser.objects.all()]

class BaseUserTest(TestCase):

    def setUp(self):
        '''Sets up our BaseUserTest by creating users, linking them
        adding some holidays and creating fake Request objects'''
        create_users(self)

        # create a new_user dict to share among tests
        self.new_user = {
            'mode': "false",
            'user_id': "new_test@user.com",
            'firstname': "New",
            'lastname': "Test",
            'user_type': "RUSER",
            'market': "BK",
            'process': "AR",
            'start_date': "2012-01-01",
            'breaklength': "00:15:00",
            'shiftlength': "07:45:00",
            'job_code': "ABCDE",
            'holiday_balance': 20
        }

        # create some random holiday data
        holidays = {
            self.linked_manager.id: list(),
            self.linked_user.id: list(),
            }
        holidays_empty = {
            self.linked_manager.id: list(),
            self.linked_user.id: list(),
            }
        for day in range(1, 32):
            holidays[self.linked_manager.id].append(random.choice(ABSENT_CHOICES)[0])
            holidays[self.linked_user.id].append(random.choice(ABSENT_CHOICES)[0])
            holidays_empty[self.linked_manager.id].append("empty")
            holidays_empty[self.linked_user.id].append("empty")
        self.holiday_data = simplejson.dumps(holidays)
        self.holiday_data_empty = simplejson.dumps(holidays_empty)

        class Request(object):
            '''Fake Request class'''
            def __init__(self, model_id):
                '''Initializor'''
                self.session = {
                    'user_id': model_id
                    }

                self.POST = {}

            def is_ajax(self):
                '''Mocked method for the django `is_ajax` method.'''
                return True

        self.linked_manager_request = Request(self.linked_manager.id)
        self.linked_teamlead_request = Request(self.linked_teamlead.id)
        self.linked_user_request = Request(self.linked_user.id)
        self.unlinked_manager_request = Request(self.unlinked_manager.id)
        self.unlinked_teamlead_request = Request(self.unlinked_teamlead.id)
        self.unlinked_user_request = Request(self.unlinked_user.id)

    def tearDown(self):
        '''Deletes our class'''
        del(self.linked_manager_request)
        delete_users(self)
        [holiday.delete() for holiday in TrackingEntry.objects.all()]

class UserTestCase(BaseUserTest):
    '''
    Tests the methods attached to user instances
    '''

    def test_Sup_TL_or_Admin(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.sup_tl_or_admin(), True)
        self.assertEquals(self.linked_manager.sup_tl_or_admin(), True)
        self.assertEquals(self.linked_teamlead.sup_tl_or_admin(), True)
        self.assertEquals(self.linked_user.sup_tl_or_admin(), False)

    def test_IsSuper(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.is_super(), True)
        self.assertEquals(self.linked_manager.is_super(), False)
        self.assertEquals(self.linked_teamlead.is_super(), False)
        self.assertEquals(self.linked_user.is_super(), False)

    def test_Super_Or_Admin(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.super_or_admin(), True)
        self.assertEquals(self.linked_manager.super_or_admin(), True)
        self.assertEquals(self.linked_teamlead.super_or_admin(), False)
        self.assertEquals(self.linked_user.super_or_admin(), False)

    def test_IsAdmin(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.is_admin(), False)
        self.assertEquals(self.linked_manager.is_admin(), True)
        self.assertEquals(self.linked_teamlead.is_admin(), False)
        self.assertEquals(self.linked_user.is_admin(), False)

    def test_Admin_or_TL(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.admin_or_tl(), False)
        self.assertEquals(self.linked_manager.admin_or_tl(), True)
        self.assertEquals(self.linked_teamlead.admin_or_tl(), True)
        self.assertEquals(self.linked_user.admin_or_tl(), False)

    def test_IsTL(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.is_tl(), False)
        self.assertEquals(self.linked_manager.is_tl(), False)
        self.assertEquals(self.linked_teamlead.is_tl(), True)
        self.assertEquals(self.linked_user.is_tl(), False)

    def test_IsUSER(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(self.linked_super_user.is_user(), False)
        self.assertEquals(self.linked_manager.is_user(), False)
        self.assertEquals(self.linked_teamlead.is_user(), False)
        self.assertEquals(self.linked_user.is_user(), True)

    def test_get_subordinates(self):
        '''Tests the user permissions-related functions.'''
        self.assertEquals(len(self.linked_super_user.get_subordinates()), 4)
        self.assertEquals(len(self.linked_manager.get_subordinates()), 9)
        self.assertEquals(len(self.linked_teamlead.get_subordinates()), 9)
        self.assertEquals(len(self.linked_user.get_subordinates()), 7)

    def testName(self):
        '''
        Should return the full name
        '''
        self.assertEquals(self.linked_user.name(), "test case")
        self.assertEquals(self.linked_manager.name(), "test case")

    def testUserType(self):
        '''
        Make sure our types return what we set them up as
        '''
        self.assertEquals(self.linked_super_user.user_type, "SUPER")
        self.assertEquals(self.linked_manager.user_type, "ADMIN")
        self.assertEquals(self.linked_teamlead.user_type, "TEAML")
        self.assertEquals(self.linked_user.user_type, "RUSER")

    def testHolidayBalanceMix(self):
        '''
        Test to make sure that the holiday balance calculates correctly
        '''
        for day in (("1", "HOLIS"), ("2", "PUWRK"), ("3", "RETRN")):
            entry = TrackingEntry(
                entry_date="2012-01-%s" % day[0],
                user_id=self.linked_user.id,
                start_time="00:00:00",
                end_time="00:00:00",
                breaks="00:00:00",
                daytype=day[1],
            )
            entry.save()

        self.assertEquals(self.linked_user.get_holiday_balance(2012), 20)

    def testHolidayBalanceAdd(self):
        '''
        Test for the holiday additional total works
        '''
        for day in (("1", "PUWRK"), ("2", "PUWRK"), ("3", "PUWRK")):
            entry = TrackingEntry(
                entry_date="2012-01-%s" % day[0],
                user_id=self.linked_user.id,
                start_time="00:00:00",
                end_time="00:00:00",
                breaks="00:00:00",
                daytype=day[1],
            )
            entry.save()

        self.assertEquals(self.linked_user.get_holiday_balance(2012), 26)

    def testHolidayBalanceDecrement(self):
        '''
        Test for the return decrement total works
        '''
        for day in (("1", "RETRN"), ("2", "RETRN"), ("3", "RETRN")):
            entry = TrackingEntry(
                entry_date="2012-01-%s" % day[0],
                user_id=self.linked_user.id,
                start_time="00:00:00",
                end_time="00:00:00",
                breaks="00:00:00",
                daytype=day[1],
            )
            entry.save()

        self.assertEquals(self.linked_user.get_holiday_balance(2012), 17)

class TrackingEntryTestCase(BaseUserTest):
    '''TrackingEntryTestCase tests the TrackingEntry's functionality'''
    def testIsNotOvertime(self):
        '''Tests an entry against several rules to make sure our
        check for whether an entry is or is not overtime is correctly
        working.'''
        for date, end in [
            ["2012-01-01", "17:00"],
            ["2012-01-02", "14:00"],
            ["2012-01-03", "16:46"],
            ["2012-01-04", "16:45"],
            ]:
            entry = TrackingEntry(
                entry_date=date,
                user_id=self.linked_user.id,
                start_time="09:00",
                end_time=end,
                breaks="00:15",
                daytype="WKDAY"
                )
            entry.full_clean()
            self.assertFalse(entry.is_overtime())

    def testIsOvertime(self):
        '''Tests an entry against several rules to make sure our
        check for whether an entry is or is not overtime is correctly
        working.'''
        for date, end in [
            ["2012-01-06", "18:01"],
            ["2012-01-07", "19:00"],
            ]:
            entry = TrackingEntry(
                entry_date=date,
                user_id=self.linked_user.id,
                start_time="09:00",
                end_time=end,
                breaks="00:15",
                daytype="WKDAY"
                )
            entry.full_clean()
            self.assertTrue(entry.is_overtime())

    def testTimeDifferencePositive(self):
        '''Tests an entry against several rules to make sure our
        check for whether an entry is or is not overtime is correctly
        working.'''
        for date, end in [
            ["2012-01-08", "18:00"],
            ["2012-01-09", "18:01"],
            ["2012-01-10", "19:00"],
            ]:
            entry = TrackingEntry(
                entry_date=date,
                user_id=self.linked_user.id,
                start_time="09:00",
                end_time=end,
                breaks="00:15",
                daytype="WKDAY"
                )
            entry.full_clean()
            self.assertTrue(entry.time_difference() > 0)

    def testTimeDifferenceNegative(self):
        '''Tests an entry against several rules to make sure our
        check for whether an entry is or is not overtime is correctly
        working.'''
        for date, end in [
            ["2012-01-11", "14:00"],
            ["2012-01-12", "16:44"],
            ["2012-01-13", "09:45"],
            ]:
            entry = TrackingEntry(
                entry_date=date,
                user_id=self.linked_user.id,
                start_time="09:00",
                end_time=end,
                breaks="00:15:00",
                daytype="WKDAY"
                )
            entry.full_clean()
            self.assertTrue(entry.time_difference() < 0)

    def testTimeDifferenceZero(self):
        '''Tests an entry against several rules to make sure our
        check for whether an entry is or is not overtime is correctly
        working.'''
        for date, end in [
            ["2012-01-11", "16:45"],
            ]:
            entry = TrackingEntry(
                entry_date=date,
                user_id=self.linked_user.id,
                start_time="09:00",
                end_time=end,
                breaks="00:15",
                daytype="WKDAY"
                )
            entry.full_clean()
            self.assertTrue(entry.time_difference() == 0)


class DatabaseTestCase(BaseUserTest):
    '''
    Class which tests the database for improper settings
    '''

    def testDuplicateError(self):
        '''
        Test which ensures that duplicate e-mail addresses
        cannot be used
        '''
        try:
            self.manager = Tbluser.objects.create(
                user_id="test.manager@test.com",
                firstname="test",
                lastname="case",
                password="password",
                user_type="ADMIN",
                market="BG",
                process="AP",
                start_date=datetime.datetime.today(),
                breaklength="00:15:00",
                shiftlength="07:45:00",
                job_code="00F20G",
                holiday_balance=20
                )
        # we're catching & ignoring duplicate entry
        # because that's what it's supposed to do
        except IntegrityError as error:
            if error[0] == DUPLICATE_ENTRY:
                pass
            else:
                raise

class AjaxTestCase(BaseUserTest):
    '''
    Class which tests the ajax request handler functions
    '''

    def testValidDeleteUserViaManager(self):
        '''
        Tests a valid delete from a manager
        '''
        self.linked_manager_request.POST['user_id'] = self.linked_user.id
        valid = delete_user(self.linked_manager_request)
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ""})
        self.assertEquals(valid.content, json)

    def testValidDeleteUserViaTeamLeader(self):
        '''
        Tests a valid delete from a teamleader
        '''

        self.linked_teamlead_request.POST['user_id'] = self.linked_user.id
        valid = delete_user(self.linked_teamlead_request)
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ""})
        self.assertEquals(valid.content, json)

    def testInvalidDeleteUser(self):
        '''
        Tests an invalid delete
        '''
        # invalid delete
        self.linked_manager_request.POST['user_id'] = 999
        invalid = delete_user(self.linked_manager_request)
        self.assertIsInstance(invalid, HttpResponse)
        json = simplejson.dumps({'success': False, 'error': "User does not exist"})
        self.assertEquals(invalid.content, json)

    def testValidAddUserViaLinkedManager(self):
        '''
        Tests the ajax add user function for a hopefully valid add
        '''

        # create the post
        self.linked_manager_request.POST = self.new_user

        # test the addition of the user and the response
        valid = useredit(self.linked_manager_request)

        # test if the user is in the database
        # if this fails, this signifies our saving mechanism
        # is borked
        test_user = Tbluser.objects.filter(user_id="new_test@user.com")

        # test if the tblauthorization has been setup
        # if this fails, this signifies our tblauth creation
        # is borked
        tblauth = Tblauthorization.objects.filter(admin=self.linked_manager.id)

        # assert the return codes
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ''})
        self.assertEquals(valid.content, json)

    def testValidAddUserViaUnLinkedManager(self):
        '''
        Tests the ajax add user function for a hopefully valid add
        '''

        # create the post
        self.unlinked_manager_request.POST = self.new_user

        # test the addition of the user and the response
        valid = useredit(self.unlinked_manager_request)

        # test if the user is in the database
        # if this fails, this signifies our saving mechanism
        # is borked
        test_user = Tbluser.objects.filter(user_id="new_test@user.com")

        # test if the tblauthorization has been setup
        # if this fails, this signifies our tblauth creation
        # is borked
        tblauth = Tblauthorization.objects.filter(admin=self.unlinked_manager.id)

        # assert the return codes
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ''})
        self.assertEquals(valid.content, json)

    def testValidAddMassHolidaysManager(self):
        '''Tests whether adding Valid holiday data to the tracker
        returns the correct response.
        '''
        # create the post
        self.linked_manager_request.POST = {
            'form_data': 'mass_holiday',
            'user_id': self.linked_user.id,
            'year': '2012',
            'month': '1',
            'mass_data': self.holiday_data
            }

        # the first time should be a virgin entry
        valid = mass_holidays(self.linked_manager_request)
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ''})
        self.assertEquals(valid.content, json)

        self.linked_manager_request.POST = {
            'form_data': 'mass_holiday',
            'user_id': self.linked_user.id,
            'year': '2012',
            'month': '1',
            'mass_data': self.holiday_data_empty
            }

        # the 2nd time should still work, but silently pass
        valid = mass_holidays(self.linked_manager_request)
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ''})
        self.assertEquals(valid.content, json)

        # create the post
        self.linked_manager_request.POST = {
            'form_data': 'mass_holiday',
            'user_id': self.linked_user.id,
            'year': '2012',
            'month': '1',
            'mass_data': self.holiday_data
            }

        # the last time
        valid = mass_holidays(self.linked_manager_request)
        self.assertIsInstance(valid, HttpResponse)
        json = simplejson.dumps({'success': True, 'error': ''})
        self.assertEquals(valid.content, json)

    def testValidAjaxDeleteHolidayEntry(self):
        '''Tests to see if the ajax endpoint for deleting a holiday
        entry is working correctly.'''

        # create the entry we want to delete
        TrackingEntry(entry_date="2012-01-01", user_id=self.linked_user.id)

        # create the post
        self.linked_user_request.POST = {
            'hidden-id': self.linked_user.id,
            'entry_date': '2012-01-01'
            }
        valid = ajax_delete_entry(self.linked_user_request)
        self.assertIsInstance(valid, HttpResponse)
        self.assertEquals(simplejson.dumps({
                "success": True,
                "error": '',
                "calendar": gen_calendar(2012, 1, 1, user=self.linked_user.id)
                }),
                valid.content)

    def testValidAjaxChangeHolidayEntry(self):
        '''Tests to see if the ajax endpoint for changing a holiday
        entry is working correctly.'''

        # create the entry we want to delete
        TrackingEntry(entry_date="2012-01-01", user_id=self.linked_user.id)

        # create the post
        self.linked_user_request.POST = {
            'entry_date': '2012-01-01',
            'start_time': '09:00',
            'end_time': '17:00',
            'daytype': 'WKDAY',
            'breaks': '00:15:00',
            'hidden-id': self.linked_user.id,
        }
        valid = ajax_change_entry(self.linked_user_request)
        self.assertIsInstance(valid, HttpResponse)
        self.assertEquals(simplejson.dumps({
                "success": True,
                "error": '',
                "calendar": gen_calendar(2012, 1, 1, user=self.linked_user.id)
                }),
                valid.content)

    def testAjaxError(self):
        '''AjaxError is a helpful method to create a JSON message
        containing an error. We test that here.'''
        valid = ajax_error("test string")
        self.assertIsInstance(valid, HttpResponse)

        self.assertEquals(valid.content, simplejson.dumps({
                    'success': False,
                    'error': 'test string'
                    })
                          )

class UtilitiesTest(TestCase):
    '''The utilties module contains several miscellanious pieces of
    functionality, we test those here.'''

    def testValidateTime(self):
        '''Time validation tests. We validate whether two time strings
        are sequential.'''
        self.assertEquals(validate_time("00:00", "00:01"), True)
        self.assertEquals(validate_time("00:00", "23:00"), True)
        self.assertEquals(validate_time("00:00", "00:00"), False)
        self.assertEquals(validate_time("23:00", "00:00"), False)
        self.assertEquals(validate_time("00:01", "00:00"), False)

    def testParseTime(self):
        '''Time parsing tests. We test whether certain times are parsed
        correctly into a list of integers representing the time.'''
        self.assertEquals(parse_time("00:01"), [0,1])
        self.assertEquals(parse_time("23:57"), [23,57])
        self.assertEquals(parse_time("12:12"), [12,12])

    def testPad(self):
        '''String padding tests, tests whether a string is correctly
        padded.'''
        self.assertEquals(pad("teststring"), "teststring")
        self.assertEquals(pad("t"), "0t")
        self.assertEquals(pad("teststring", amount=20),
                          "0000000000teststring")
        self.assertEquals(pad("teststring", padchr='1', amount=20),
                          "1111111111teststring")
        self.assertEquals(pad("t", padchr="1" ),
                          "1t")

    def testFloat_to_time(self):
        '''Float to time conversion.'''
        self.assertEquals(float_to_time(0.1), "00:06")
        self.assertEquals(float_to_time(0.2), "00:12")
        self.assertEquals(float_to_time(0.3), "00:18")
        self.assertEquals(float_to_time(0.4), "00:24")
        self.assertEquals(float_to_time(0.5), "00:30")
        self.assertEquals(float_to_time(1.0), "01:00")
        self.assertEquals(float_to_time(5.0), "05:00")

    def testGenerateSelect(self):
        '''We have functionality to convert Python datastructures to
        HTML select boxes. Testing the output is correct.'''
        output = generate_select((
            ('val1', 'Value One'),
            ('val2', 'Value Two'),
            ('val3', 'Value Three')
        ))

        string = '''<select id="">
\t<option value="val1">Value One</option>
\t<option value="val2">Value Two</option>
\t<option value="val3">Value Three</option>
</select>'''
        self.assertEquals(output, string)

class FrontEndTest(LiveServerTestCase):
    '''FrontEndTest uses Selenium to navigate the front-end of the
    application to test the Javascript and the interaction between
    that and the back-end code.'''

    def setUp(self):
        '''Sets up our class.'''
        create_users(self)

    def tearDown(self):
        '''Deletes our class.'''
        delete_users(self)
        try:
            self.accessURL("/edit_profile/")
            self.driver.get_element_by_id("logout-btn").click()
            self.accessURL("")
        except:
            pass

    @classmethod
    def setUpClass(cls):
        '''Sets up the attributes for the whole test suite.'''
        cls.driver = WebDriver()
        super(FrontEndTest, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        '''Sets up the attributes for the whole test suite.'''
        super(FrontEndTest, cls).tearDownClass()
        delete_users(cls)
        cls.driver.quit()

    @skipUnless(SELENIUM_AVAILABLE, "These tests require Selenium to be installed.")
    def test_AccessRights(self):
        '''Tests whether the front-end locks certain user types out
        of the things they're not supposed to use.'''
        self.user_login()

        # selenium doesn't give direct access to the response
        # code so we look for some element.

        for url in ["/admin_view/", "/yearview/", "/user_edit/", "/holiday_planning/"]:
            self.accessURL(url)
            time.sleep(1)
            self.assertRaises(NoSuchElementException, self.driver.find_element_by_id, "logout-btn")

    @skipUnless(SELENIUM_AVAILABLE, "These tests require Selenium to be installed.")
    def test_WeekendButtonHasNoFunction(self):
        '''
        This ensures that the weekend button simply servers to show the
        user what the element represents. We don't want the element to
        have any use other than that, otherwise we could end up with
        weekends ending up being stored in the database.
        '''
        self.manager_login()
        # wait to be logged in
        time.sleep(2)
        self.accessURL("/holiday_planning/")
        holiday_table = self.driver.find_element_by_id("holiday-table")
        cells = holiday_table.find_elements_by_tag_name("td")

        clicked_cells = []
        for cell in cells:
            if cell.get_attribute("usrid") == "1":
                if cell.get_attribute("class") != "WKEND":
                    clicked_cells.append(cell)
                    cell.click()
        holiday_buttons = self.driver.find_element_by_id("holiday-buttons")
        buttons = holiday_buttons.find_elements_by_tag_name("td")
        for button in buttons:
            if "WKEND" in button.get_attribute("class"):
                button.click()
        for cell in clicked_cells:
            self.assertFalse("WKEND" in cell.get_attribute("class"))

    @skipUnless(SELENIUM_AVAILABLE, "These tests require Selenium to be installed.")
    def test_SubmitHolidays(self):
        '''Tests that submitting holidays works.'''
        self.manager_login()
        # wait to be logged in
        time.sleep(2)

        self.accessURL("/holiday_planning/")
        holiday_table = self.driver.find_element_by_id("holiday-table")
        cells = holiday_table.find_elements_by_tag_name("td")
        count = 0
        for cell in cells:
            if cell.get_attribute("usrid"):
                if cell.get_attribute("class") != "WKEND":
                    cell.click()
                    count += 1
                    # we don't need that many to test
                    if count == 30:
                        break
        self.click_daytype("HOLIS")
        self.driver.find_element_by_id("submit_all").click()
        time.sleep(5)
        self.driver.switch_to_alert().accept()
        self.assertEquals(len(TrackingEntry.objects.all()), count)

    @skipUnless(SELENIUM_AVAILABLE, "These tests require Selenium to be installed.")
    def test_HolidayPageStateCheck(self):
        '''Inserts some state into the table using a previous method
        then we check that the state doesn't follow the application
        around.

        This test came around from a bug whereby inserting data on
        one month, switching to another and submitting again would
        result in the first month's data being used for the second's.
        '''
        self.manager_login()
        time.sleep(2)

        self.accessURL("/holiday_planning/")
        self.goto_month("2")
        time.sleep(3)
        holiday_table = self.driver.find_element_by_id("holiday-table")
        cells = holiday_table.find_elements_by_tag_name("td")
        count = 0
        for cell in cells:
            if cell.get_attribute("usrid"):
                if cell.get_attribute("class") != "WKEND":
                    cell.click()
                    count += 1
                    # we don't need that many to test
                    if count == 10:
                        break
        self.click_daytype("HOLIS")
        inputs = self.driver.find_elements_by_tag_name("input")
        for input_ in inputs:
            if "button_2" in input_.get_attribute("id"):
                input_.click()
                time.sleep(2)
                self.driver.switch_to_alert().accept()
                break
        self.goto_month("3")
        time.sleep(2)
        inputs = self.driver.find_elements_by_tag_name("input")
        for input_ in inputs:
            if "button_" in input_.get_attribute("id"):
                input_.click()
                time.sleep(2)
                self.driver.switch_to_alert().accept()
                break
        self.assertEquals(len(TrackingEntry.objects.all()), count)

    @skipUnless(SELENIUM_AVAILABLE, "These tests require Selenium to be installed.")
    def test_Logins(self):
        '''Tests all users can login properly.'''
        # login
        self.user_login()
        # if this raises it means we're logged in.
        self.assertRaises(NoSuchElementException, self.driver.find_element_by_id, "error")
        self.driver.find_element_by_id("logout-btn").click()
        # once again with a manager
        self.manager_login()
        self.assertRaises(NoSuchElementException, self.driver.find_element_by_id, "error")
        self.driver.find_element_by_id("logout-btn").click()

    def login(self, who):
        '''Helper method to log in a specific user.'''
        self.driver.get(self.live_server_url)
        self.driver.find_element_by_id("login-user").send_keys(who.user_id)
        self.driver.find_element_by_id("login-password").send_keys(who.password)
        self.driver.find_element_by_id("add_button").click()
    def user_login(self):
        '''Helper method to login a user.'''
        self.login(self.linked_user)
    def manager_login(self):
        '''Helper method to login a manager.'''
        self.login(self.linked_manager)

    def accessURL(self, url):
        '''Helper to push the browser to a specific URL.'''
        self.driver.get("%s%s" % (self.live_server_url, url))

    def click_daytype(self, daytype):
        '''Clicks a daytype button.'''
        holiday_buttons = self.driver.find_element_by_id("holiday-buttons")
        buttons = holiday_buttons.find_elements_by_tag_name("td")
        for button in buttons:
            if daytype in button.get_attribute("class"):
                button.click()

    def goto_month(self, num):
        '''Moves the calendar to the selected month.'''
        select = self.driver.find_element_by_id("month_select")
        options = select.find_elements_by_tag_name("option")
        for option in options:
            if option.get_attribute("value") == num:
                option.click()
                break

class MiddlewareTest(TestCase):
    '''Tests the MiddleWare.'''
    def setUp(self):
        '''Sets up the class.'''
        self.ehandler = UnreadablePostErrorMiddleware()
    def test_handles_unreadable_post_error_correctly(self):
        '''Unreadable Post is raised when a post is aborted part-way
        through. It's harmless and should be ignored. This middleware
        allows us to not have to wrap entire methods in try/catch
        blocks.'''
        self.assertRaises(
            Http404,
            self.ehandler.process_exception, {}, UnreadablePostError()
            )

FrontEndTest = None
