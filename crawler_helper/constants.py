import re

govsi_regex = re.compile(".*\.gov\.si$")  # regex to match URLs with the .gov.si domain
full_url_regex = re.compile("^http[s]?:\/\/(www\.)?.+\..+")  # regex to match URL structure -> https://www.xyz.com
"""
Regex to match JS redirect calls in format of e.g.: location.href = "/about.html". 
The URL is stored in group 3
"""
navigation_assign_regex = re.compile(".*(.)?location(.href)?\ =\ [\"\'](.*)[\"\']")

"""
Regex to match JS redirect calls in format of e.g.: location.assign('/about.html'). 
The URL is stored in group 4
"""
navigation_func_regex = re.compile(".*(.)?location(.href)?.(.*)\([\"\'](.*)[\"\']\)")
USER_AGENT = "fri-wier-besela"
default_domain_delay = 5  # seconds
