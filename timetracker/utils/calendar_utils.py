"""
Module for collecting the utility functions dealing with mostly calendar
tasks, processing dates and creating time-based code.
"""

import random
import datetime
import calendar as cdr

from django.core.handlers.wsgi import WSGIRequest
from django.http import Http404, HttpResponse
from django.db import IntegrityError
from django.forms import ValidationError
import simplejson

from timetracker.tracker.models import TrackingEntry, Tbluser
from timetracker.tracker.models import Tblauthorization as Tblauth
from timetracker.utils.database_errors import DUPLICATE_ENTRY
from timetracker.utils.datemaps import MONTH_MAP

def pad(string, padchr='0', amount=2):
    """
    Pads a string
    """
    string = str(string)

    if len(str(string)) < amount:
        pre = padchr * (amount - len(string))
        return pre+string

    return string

def get_request_data(form, request):

    """
    Given a form and a request object we pull out
    from the request what the form defines.

    i.e.

    form = {
        'data1': None
    }

    get_request_data(form, request) will then fill
    that data with what's in the request object.
    """

    data = dict()

    # get our form data
    for key in form:
        data[key] = request.POST.get(key, None)

    # get the user id from the session
    data['user_id'] = request.session['user_id']

    return data

def validate_time(start, end):

    """
    Validates the times given
    """

    shour, sminute = parse_time(start)
    ehour, eminute = parse_time(end)

    return (datetime.time(shour, sminute)
            < datetime.time(ehour, eminute))

def parse_time(timestring, type_of=int):

    """
    Given a time string will return a tuple of ints,
    i.e. "09:44" returns (9, 44) with the default args,
    you can pass any function to the type argument.
    """

    return map(type_of, timestring.split(":"))


def calendar_wrapper(function):
    """
    Decorator which checks if the calendar function was
    called as an ajax request or not, if so, then the
    the wrapper constructs the arguments for the call
    from the POST items
    """

    def inner(*args, **kwargs):
        """
        Checks argument length and constructs the call
        based on that.
        """

        if isinstance(args[0], WSGIRequest):
            request = args[0]
            try:
                eeid = request.POST.get('eeid', None)
                json_dict = {
                    'success': True,
                    'calendar': function(user=eeid)
                }
                return HttpResponse(simplejson.dumps(json_dict))

            except Exception as e:
                return HttpResponse(str(e))

        else:
            # if the function was called from a view
            # let it just do it's thing
            return function(*args, **kwargs)

    return inner

@calendar_wrapper
def gen_calendar(year=datetime.datetime.today().year,
                 month=datetime.datetime.today().month,
                 day=datetime.datetime.today().day,
                 user=None):

    """
    Returns a HTML calendar, calling a database user to get their day-by-day
    entries and gives each day a special CSS class so that days can be styled
    individually.

    The generated HTML should be 'pretty printed' as well, so the output code
    should be pretty readable.
    """

    # django passes us Unicode strings
    year, month, day = int(year), int(month), int(day)

    if month-1 not in MONTH_MAP.keys():
        raise Http404

    # if we've generated December, link to the next year
    if month + 1 == 13:
        next_url = '"/calendar/%s/%s"' % (year + 1, 1)
    else:
        next_url = '"/calendar/%s/%s"' % (year, month + 1)

    # if we've generated January, link to the previous year
    if month - 1 == 0:
        previous_url = '"/calendar/%s/%s"' % (year - 1, 12)
    else:
        previous_url = '"/calendar/%s/%s"' % (year, month - 1)


    # user_id came from sessions or the ajax call
    # so this is pretty safe
    database = Tbluser.objects.get(id__exact=user)

    # pull out the entries for the given month
    try:
        database = TrackingEntry.objects.filter(
            user=database.id,
            entry_date__year=year,
            entry_date__month=month
            )

    except TrackingEntry.DoesNotExist:
        # it seems Django still follows through with the assignment
        # when it raises an error, this is actually quite good because
        # we can treat the query set like normal
        pass

    # create a semi-sparsely populated n-dimensional
    # array with the month's days per week
    calendar_array = cdr.monthcalendar(
        int(year),
        int(month)
    )

    # creating a list holder for the strings
    # this is faster than concatenating the
    # strings as we go.
    cal_html = list()
    to_cal = cal_html.append

    # create the table header
    to_cal("""<table id="calendar" border="1">\n\t\t\t""")

    to_cal("""<tr>
                <td class="table-header" colspan="2">
                  <a class="table-links" href={0}>&lt;</a>
                </td>

                <td class="table-header" colspan="3">{2}</td>

                <td class="table-header" colspan="2">
                  <a class="table-links" href={1}>&gt;</a>
                </td>
              </tr>\n""".format(previous_url,
                                next_url,
                                MONTH_MAP[int(month)-1][1]
                        )
           )

    # insert day names
    to_cal("""\n\t\t\t<tr>
                <td class=day-names>Mon</td>
                <td class=day-names>Tue</td>
                <td class=day-names>Wed</td>
                <td class=day-names>Thu</td>
                <td class=day-names>Fri</td>
                <td class=day-names>Sat</td>
                <td class=day-names>Sun</td>
              </tr>\n""")

    # each row in the calendar_array is a week
    # in the calendar, so create a new row
    for week_ in calendar_array:
        to_cal("""\n\t\t\t<tr>\n""")

        for _day in week_:

            # the calendar_array fills extraneous days
            # with 0's, we can catch that and treat either
            # end of the calendar differently in the CSS
            if _day != 0:
                emptyclass = 'day-class empty-day'
            else:
                emptyclass = 'empty'

            # we've got the month in the query set,
            # so just query that set for individual days
            try:
                # get all the data from our in-memory query-set.
                data = database.get(entry_date__day=_day)

                # Pass these to the page so that the jQuery functions
                # get the function arguments to edit those elements
                vals = [
                    data.start_time.hour,
                    data.start_time.minute,
                    str(data.start_time)[0:5],
                    data.end_time.hour,
                    data.end_time.minute,
                    str(data.end_time)[0:5],
                    data.entry_date,
                    data.daytype,
                    _day,
                    data.id,
                    data.breaks.minute,
                    str(data.breaks)[0:5]
                    ]

                to_cal("""\t\t\t\t
                       <td onclick="toggleChangeEntries({0}, {1}, '{2}',
                                                        {3}, {4}, '{5}',
                                                        '{6}', '{7}', {9},
                                                        {10}, '{11}')"
                           class="day-class {7}">{8}</td>\n""".format(*vals)
                       )

            except TrackingEntry.DoesNotExist:

                # For clicking blank days to input the day quickly into the
                # box. An alternative to the datepicker
                if _day != 0:
                    entry_date_string = '-'.join(map(pad,
                                                     [year, month, _day]
                                                     )
                                                )
                else:
                    entry_date_string = ''

                # we don't want to write a 0 in the box
                _day = '&nbsp' if _day == 0 else _day

                # write in the box and give the empty boxes a way to clear
                # the form
                to_cal("""\t\t\t\t<td onclick="hideEntries('{0}')"
                    class="{1}">{2}</td>\n""".format(
                                                  entry_date_string,
                                                  emptyclass,
                                                  _day)
                                              )

        # close up that row
        to_cal("""\t\t\t</tr>\n""")

    # close up the table
    to_cal("""\n</table>""")

    # join up the html and push it back
    return ''.join(cal_html)

def json_response(func):

    """
    Decorator function that when applied to a function which
    returns some json data will be turned into a HttpResponse

    This is useful because the call site can literally just
    call the function as it is without needed to make a http-
    response.
    """

    def inner(request):

        """
        Grabs the request object on the decorated and calls
        it
        """

        return HttpResponse(simplejson.dumps(func(request)),
                            mimetype="application/javscript")
    return inner

def request_check(func):

    """
    Decorator to check an incoming request against a few rules
    """

    def inner(request):

        """
        Pulls the request object off the decorated function
        """

        if not request.is_ajax():
            raise Http404

        if not request.session.get('user_id', None):
            # if there is no user id in the session
            # something weird is going on
            raise Http404

        return func(request)

    return inner


@request_check
@json_response
def ajax_add_entry(request):

    '''
    Adds a calendar entry asynchronously
    '''

    # object to dump form data into
    form = {
        'entry_date': None,
        'start_time': None,
        'end_time': None,
        'daytype': None,
        'breaks': None
    }

    # get the form data from the request object
    form.update(get_request_data(form, request))

    # create objects to put our data into
    json_data = dict()

    try:
        # server-side time validation
        if not validate_time(form['start_time'], form['end_time']):
            json_data['error'] = "Start time after end time"
            return json_data
    except ValueError:
        json_data['error'] = "Date Error"
        return json_data

    try:
        entry = TrackingEntry(**form)
        entry.save()
    except IntegrityError as error:
        if error[0] == DUPLICATE_ENTRY:
            json_data['error'] = "There is a duplicate entry for this value"
        else:
            json_data['error'] = str(error)
        return json_data

    year, month, day = map(int,
                           form['entry_date'].split("-")
                           )

    calendar = gen_calendar(year, month, day,
                            form['user_id'])

    # if all went well
    json_data['success'] = True
    json_data['calendar'] = calendar
    return json_data

@request_check
@json_response
def ajax_delete_entry(request):
    """
    Asynchronously deletes an entry
    """

    form = {
        'hidden-id': None,
        'entry_date': None
    }

    # get the form data from the request object
    form.update(get_request_data(form, request))

    # create our json structure
    json_data = dict()

    if form['hidden-id']:
        try:
            # get the user and make sure that the user
            # assigned to the TrackingEntry is the same
            # as what's requesting the deletion
            user = Tbluser.objects.get(id__exact=form['user_id'])
            entry = TrackingEntry(id=form['hidden-id'],
                                  user=user)
            entry.delete()
        except Exception as error:
            json_data['error'] = str(error)
            return json_data

    year, month, day = map(int,
                           form['entry_date'].split("-")
                           )

    calendar = gen_calendar(year, month, day,
                            user=form['user_id'])

    # if all went well
    json_data['success'] = True
    json_data['calendar'] = calendar
    return json_data

@json_response
def ajax_error(error):

    """
    Returns a HttpResponse with JSON as a payload with the error
    code as the string that the function is called with
    """

    return {
        'success': False,
        'error': error
        }

@request_check
@json_response
def ajax_change_entry(request):

    '''
    Changes a calendar entry asynchronously
    '''

    # object to dump form data into
    form = {
        'entry_date': None,
        'start_time': None,
        'end_time': None,
        'daytype': None,
        'breaks': None,
        'hidden-id': None,
        'breaks': None

    }

    # get the form data from the request object
    form.update(get_request_data(form, request))

    # create objects to put our data into
    json_data = dict()

    try:
        # server-side time validation
        if not validate_time(form['start_time'], form['end_time']):
            json_data['error'] = "Start time after end time"
            return json_data
    except ValueError:
        json_data['error'] = "Date Error"
        return json_data

    if form['hidden-id']:
        try:
            # get the user and make sure that the user
            # assigned to the TrackingEntry is the same
            # as what's requesting the change
            user = Tbluser.objects.get(id__exact=form['user_id'])
            entry = TrackingEntry(id=form['hidden-id'],
                                  user=user)

            # change the fields on the retrieved entry
            entry.entry_date = form['entry_date']
            entry.start_time = form['start_time']
            entry.end_time = form['end_time']
            entry.daytype = form['daytype']
            entry.breaks = form['breaks']

            entry.save()

        except Exception as error:
            json_data['error'] = str(error)
            return json_data

    year, month, day = map(int,
                           form['entry_date'].split("-")
                           )

    calendar = gen_calendar(year, month, day,
                            form['user_id'])

    # if all went well
    json_data['success'] = True
    json_data['calendar'] = calendar
    return json_data

def admin_check(func):

    """
    Wrapper to see if the view is being called as an admin
    """

    def inner(request, **kwargs):
        admin_id = request.session.get('user_id', None)

        if not admin_id:
            raise Http404

        return func(request, **kwargs)

    return inner

@request_check
@admin_check
@json_response
def get_user_data(request):
    """
    Returns a user as a json object
    """

    user = Tbluser.objects.get(
        id__exact=request.POST.get('user_id', None)
    )

    json_data = {
        'success': False
    }

    if user:

        json_data = {
            'success': True,
            'username': user.user_id,
            'firstname': user.firstname,
            'lastname': user.lastname,
            'market': user.market,
            'process': user.process,
            'user_type': user.user_type,
            'start_date': str(user.start_date),
            'breaklength': str(user.breaklength),
            'shiftlength': str(user.shiftlength),
            'job_code': user.job_code,
            'holiday_balance': user.holiday_balance
        }

    return json_data

@request_check
@admin_check
@json_response
def delete_user(request):
    """
    Asynchronously deletes a user
    """

    user_id = request.POST.get('user_id', None)

    json_data = {
        'success': False,
        'error': 'Missing user',
    }

    if user_id:
        try:
            user = Tbluser.objects.get(id=user_id)
            user.delete()
        except Tbluser.DoesNotExist:
            json_data['error'] = "User does not exist"
            return json_data

        json_data['success'] = True
        return json_data

    return json_data


@request_check
@admin_check
@json_response
def add_user(request):

    """
    Adds a user to the database asynchronously
    """

    # create a random enough password
    password = ''.join([chr(random.randint(33, 90)) for _ in range(12)])
    data = {'password': password}

    # get the data off the request object
    for item in request.POST:
        if item != "form_type":
            data[item] = request.POST[item]

    json_data = {
        'success': False,
        'error': ''
    }

    try:
        # create the user
        user = Tbluser(**data)
        user.save()
        # link the user to the admin
        admin = Tblauth.objects.get(id=request.session.get('user_id'))
        admin.users.add(user)
        admin.save()
    except IntegrityError as error:
        if error[0] == DUPLICATE_ENTRY:
            json_data['error'] = "Duplicate entry"
            return json_data
        else:
            json_data['error'] = str(error)
            return json_data
    except ValidationError:
        json_data['error'] = "Invalid Data."
        return json_data
    except Tbluser.DoesNotExist:
        json_data['error'] = "User doesn't exist. Already deleted?"

    json_data['success'] = True
    return json_data


@request_check
@admin_check
@json_response
def mass_holidays(request):
    """
    Adds a holidays for a specific user en masse
    """

    json_data = {
        'success': False,
        'error': ''
    }

    form_data = {
        'year': None,
        'month': None,
        'user_id': None
    }

    for key in form_data:
        form_data[key] = request.POST.get(key, None)

    holiday_data = simplejson.loads(request.POST.get('holiday_data'))

    for entry in holiday_data.items():

        day = str(int(entry[0])) # conversion to int->str removes newlines easier
        year = form_data['year']
        month = form_data['month']
        date = '-'.join([year, month, day])

        if entry[1] == "empty" or (not len(entry[1])):
            try:
                removal_entry = TrackingEntry.objects.get(
                    entry_date=date,
                    user_id=form_data['user_id']
                    )
                removal_entry.delete()
            except TrackingEntry.DoesNotExist:
                pass
        else:
            try:
                time_str = "00:00:00"
                new_entry = TrackingEntry(
                    user_id=form_data['user_id'],
                    entry_date=date,
                    start_time=time_str,
                    end_time=time_str,
                    breaks=time_str,
                    daytype=entry[1]
                    )
                new_entry.save()
            except IntegrityError as error:
                if error[0] == DUPLICATE_ENTRY:
                    change_entry = TrackingEntry.objects.get(
                        user_id=form_data['user_id'],
                        entry_date=date
                        )
                    change_entry.daytype = entry[1]
                    change_entry.save()
                else:
                    raise Exception(error)
            except Exception as error:
                json_data['error'] = str(error)
                return json_data

    json_data['success'] = True
    return json_data
