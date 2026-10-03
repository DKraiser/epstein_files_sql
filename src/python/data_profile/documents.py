import polars as pl
import re
from python.defines.dataset_passport import LOCAL_FILES_PATHS
from datetime import datetime


DOCUMENTS_PATHS = LOCAL_FILES_PATHS["documents"]

POSTGRES_DATE_FORMATS = (
    "%Y-%m-%d",     # 2017-3-1
    "%B %d, %Y",    # March 3, 2017
    "%m/%d/%Y",     # 1/8/1999
    "%m/%d/%y",     # 1/8/99
    "%Y-%b-%d",     # 1999-Jan-08
    "%b-%d-%Y",     # Jan-08-1999
    "%d-%b-%Y",     # 08-Jan-1999
    "%y-%b-%d",     # 99-Jan-08
    "%d-%b-%y",     # 08-Jan-99
    "%b-%d-%y",     # Jan-08-99
    "%Y%m%d",       # 19990108
    "%y%m%d",       # 990108
    "%Y.%j",        # 1999.008
)

UNAMBIGOUSLY_PARSEABLE_DATE_FORMATS = (
    "%a %m/%d/%Y",              # Tue 1/3/2017
    "%a %m-%d-%Y",              # Tue 1-3-2017
    "%a %m.%d.%Y",              # Tue 1.3.2017
    "%a %b %d, %Y",             # Sun Mar 2, 2014
    "%b, %d %a %Y",             # Sun, 2 Mar 2014
    "%a %m/%d/%Y %I:%M:%S %p",  # Mon 8/12/2013 5:30:56 PM
    "%B %d, %Y",                # March 3, 2017
    "%B %d %Y",                 # March 3 2017
    "%B %d, %Y",                # March 3, 2017

    
    "%m-%d-%Y",                 # 3-8-2017
    "%m.%d.%Y",                 # 3.8.2017
    "%m,%d,%Y",                 # 3,8,2017
    "%m %d %Y",                 # 3 8 2017
    
    "%m-%d-%y",                 # 3-8-2017                 
    "%m.%d.%y",                 # 3.8.2017
    "%m,%d,%y",                 # 3,8,2017
    "%m %d %y",                 # 3 8 2017                 
                                
    "%Y/%m/%d",
    "%Y.%m.%d",

    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",

    # 20 Feb 2014
    "%d %b %Y",
    # 20 February 2014
    "%d %B %Y",
    # Feb 17, 2015
    "%b %d, %Y",
    # Feb 17 2015
    "%b %d %Y",
    # February 17 2015
    "%B %d %Y",
    # Thu, 12 Nov 2009
    "%a, %d %b %Y",
    # Thu, Nov 12, 2009
    "%a, %b %d, %Y",
    # Thu Nov 12 2009
    "%a %b %d %Y",
    # Thu 12 Nov 2009
    "%a %d %b %Y",
    # Thu, 01 Oct 2020 19:21:48 +0000
    "%a, %d %b %Y %H:%M:%S %z",
    # Fri, 22 Oct 2010 22:17:07
    "%a, %d %b %Y %H:%M:%S",
    # Sun Jan 30 06:19:13 2011
    "%a %b %d %H:%M:%S %Y",
    # 05JUL18
    "%d%b%y",
    # 12232011
    "%m%d%Y",
    # Jan. 28, 2018
    "%b. %d, %Y",
    # 13/08/19
    "%d/%m/%y",
    # 13/08/2019
    "%d/%m/%Y",
    # 05 Jul 15
    "%d %b %y",
    # 23 Apr 15
    "%d %b %y",
    # Thursday, June 27 2013 02:56 PM
    "%a, %b %d %Y %I:%M %p",
    # Sunday, July 9, 2017 4:45 PM
    "%a, %b %d, %Y %I:%M %p",
    # Friday, August 22, 2014 5:37 PM
    "%a, %b %d, %Y %I:%M %p",
    # Mon, Dec 18, 2012 2:45 pm
    "%a, %b %d, %Y %I:%M %p",
    # Tue, Dec. 19, 2017
    "%a, %b. %d, %Y",
    # Mon, Feb. 13, 2017
    "%a, %b. %d, %Y",
    # Sat. Dec. 16, 2017
    "%a. %b. %d, %Y",
    # Thu, 9/15/2011
    "%a, %m/%d/%Y",
    # Sat, 10/16/2010 1:54:12 AM
    "%a, %m/%d/%Y %I:%M:%S %p",
    # 8/22/2008 5:31:33 PM
    "%m/%d/%Y %I:%M:%S %p",
    # 11/26/21, 6:53 PM
    "%m/%d/%y, %I:%M %p",
    # 3/5/25, 8:06 AM
    "%m/%d/%y, %I:%M %p",
    # 2019-07-23T17:37:02+0000
    "%Y-%m-%dT%H:%M:%S%z",
    # 20120606T120702Z
    "%Y%m%dT%H%M%SZ",
    # 2020/01/06 13:30
    "%Y/%m/%d %H:%M",
    # 2019/08/12 13:17
    "%Y/%m/%d %H:%M",
    # 25.06.18
    "%d.%m.%y",
    # 06-04-'09
    "%d-%m-'%y",
    # Wed Nov 30 07:40:22 EST 2022
    "%a %b %d %H:%M:%S %Z %Y",
    # Wed Nov 30 18:23:54 +0000 2022
    "%a %b %d %H:%M:%S %z %Y",
    # 2010-02-10T01:33:54
    "%Y-%m-%dT%H:%M:%S",
    # Thu Dec 16 1:35:39 PM 2010
    "%a %b %d %I:%M:%S %p %Y",
    # Sat Jan 14 2012 1:02:55 PM
    "%a %b %d %Y %I:%M:%S %p",
    # Sunday, April 18 2009
    "%a, %b %d %Y",
    # Wednesday, May 18 2011
    "%a, %b %d %Y",
    # Thursday, December 18 2014
    "%a, %b %d %Y",
    # Thursday 09 April, 2015
    "%a %d %b, %Y",
    # Fri Sep 7/2012
    "%a %b %d/%Y",
    # Wed Mar 7/2012
    "%a %b %d/%Y",
    # Tue 26/Oct/2010
    "%a %d/%b/%Y",
    # Sat 20/10/2012
    "%a %d/%m/%Y",
    # 09/Feb/1999
    "%d/%b/%Y",
    # 26 08 2017
    "%d %m %Y",
    # April-01-2011
    "%B-%d-%Y",
    # Jan-18, 2011
    "%b-%d, %Y",
)

# Date-related notations that cannot determine one complete calendar date.
AMBIGOUSLY_PARSEABLE_DATE_FORMATS = (
    # Feb 4
    "%b %d",
    # Apr 2011
    "%b %Y",
    # July 2011
    "%B %Y",
    # MAR 99
    "%b %y",
    # 05/05
    "%m/%d",
    # May 01, 2005 - May 31, 2005
    "%b %d, %Y - %b %d, %Y",
    # 4/1/2017 - 5/31/2017
    "%m/%d/%Y - %m/%d/%Y",
    # 9/1/10 to 9/30/10
    "%m/%d/%y to %m/%d/%y",
    # 05/13/13 - 06/11/13
    "%m/%d/%y - %m/%d/%y",
    # 10/03/04 - 03/01/05
    "%m/%d/%y - %m/%d/%y",
    # 12/01/06 TO 12/31/06
    "%m/%d/%y TO %m/%d/%y",
    # Apr 01, 2017 - Apr 30, 2017
    "%b %d, %Y - %b %d, %Y",
    # Apr 01 2015-Apr 30 2015
    "%b %d %Y-%b %d %Y",
    # Mar 2014 - Apr 2014
    "%b %Y - %b %Y",
    # September/October 2015
    "%B/%B %Y",
    # 1992-1993
    "%Y-%Y",
    # Sat May 5
    "%a %b %d",
    # Mon Jun 27 9:20:01 AM
    "%a %b %d %I:%M:%S %p",
    # Tue May 8 20:05 PM
    "%a %b %d %H:%M %p",
    # Thu Jan 3
    "%a %b %d",
    # Tues Aug 9
    "%a %b %d",
    # Thu Mar 15
    "%a %b %d",
    # Thu Oct 11 2:49:48 PM
    "%a %b %d %I:%M:%S %p",
    # Sat Apr 13 5:11 PM
    "%a %b %d %I:%M %p",
    # Thursday, 12:49:51 PM
    "%a, %I:%M:%S %p",
    # September 20 and 21
    "%B %d and %d",
    # April 5-9
    "%B %d-%d",
    # August 10-31, 2013
    "%B %d-%d, %Y",
    # April 23/24, 2018
    "%B %d/%d, %Y",
    # 1998-09
    "%Y-%m",
    # 2006
    "%Y",
)

WEEKDAY_REPLACEMENTS = {
    "Monday": "Mon",
    "Mon": "Mon",

    "Tuesday": "Tue",
    "Tues": "Tue",
    "Tue": "Tue",

    "Wednesday": "Wed",
    "Wed": "Wed",

    "Thursday": "Thu",
    "Thurs": "Thu",
    "Thur": "Thu",
    "Thu": "Thu",

    "Friday": "Fri",
    "Fri": "Fri",

    "Saturday": "Sat",
    "Sat": "Sat",

    "Sunday": "Sun",
    "Sun": "Sun",
}

MONTH_REPLACEMENTS = {
    "January": "Jan",
    "Jan": "Jan",
    "Januar": "Jan",

    "February": "Feb",
    "Feb": "Feb",
    "Februar": "Feb",

    "March": "Mar",
    "Mar": "Mar",
    "März": "Mar",

    "April": "Apr",
    "Apr": "Apr",

    "May": "May",

    "June": "Jun",
    "Jun": "Jun",
    "Juni": "Jun",

    "July": "Jul",
    "Jul": "Jul",
    "Juli": "Jul",

    "August": "Aug",
    "Aug": "Aug",

    "September": "Sep",
    "Sep": "Sep",
    "Sept": "Sep",

    "October": "Oct",
    "Oct": "Oct",
    "Oktober": "Oct",

    "November": "Nov",
    "Nov": "Nov",

    "December": "Dec",
    "Dec": "Dec",
    "Dezember": "Dec",
}

def is_postgres_date(value: str) -> bool:
    for fmt in POSTGRES_DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass

    return False

def replace_weekday_month(value: str) -> str:
    for weekday, replacement in WEEKDAY_REPLACEMENTS.items():
        value = value.replace(weekday, replacement).replace(weekday.lower(), replacement).replace(weekday.upper(), replacement)

    for month, replacement in MONTH_REPLACEMENTS.items():
        value = value.replace(month, replacement).replace(month.lower(), replacement).replace(month.upper(), replacement)

    return re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", value, flags=re.IGNORECASE)

def is_parseable_date(value: str) -> bool: 
    value = replace_weekday_month(value)
    for fmt in UNAMBIGOUSLY_PARSEABLE_DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass

    return False

def is_ambigously_parseable_date(value: str) -> bool:
    value = replace_weekday_month(value)
    if any(separator in value for separator in (" - ", " to ", " TO ", " through ")):
        return True
    if re.fullmatch(r"Q[1-4] \d{4}", value):
        return True
    for fmt in AMBIGOUSLY_PARSEABLE_DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except (ValueError, re.error):
            pass

    return False

def filekeys_checks() -> None:
    filekeys = (
        pl.scan_parquet(DOCUMENTS_PATHS)
        .select("file_key")
        .drop_nulls()
        .collect()["file_key"]
    )
    filekeys_list = filekeys.to_list()

    # All file keys are unique
    print(f"Count of keys: {len(filekeys_list)}")
    print(f"Count of unique keys: {len(filekeys.unique().to_list())}")

def dates_checks() -> None:
    dates = (
        pl.scan_parquet(DOCUMENTS_PATHS)
        .select("date")
        .drop_nulls()
        .unique()
        .collect()["date"]
        .to_list()
    )

    valid_dates_count = 0
    parseable_dates_count = 0
    ambiguously_parseable_dates_count = 0
    not_parseable_dates_count = 0

    not_parseable_dates = list[str]()
    for date in dates: 
        if (is_postgres_date(date)):
            valid_dates_count += 1
        elif (is_parseable_date(date)):
            parseable_dates_count += 1
        elif (is_ambigously_parseable_date(date)):
            ambiguously_parseable_dates_count += 1
        else:
            not_parseable_dates_count += 1
            not_parseable_dates.append(date)

    print(f"valid_dates_count: {valid_dates_count}")
    print(f"parseable_dates_count: {parseable_dates_count}")
    print(f"ambiguously_parseable_dates_count: {ambiguously_parseable_dates_count}")
    print(f"not_parseable_dates_count: {not_parseable_dates_count}")
    print()
    for i in not_parseable_dates:
        print(i)

    

def main() -> None:
    # filekeys_checks()
    dates_checks()
    
if (__name__ == "__main__"):
    main()
