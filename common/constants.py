import re

govsi_regex = re.compile(".*\.gov\.si$")  # regex to match URLs with the .gov.si domain

"""
Regex to match full URL structure -> https://www.xyz.com

Looks for url schema http:// or https:// -> http[s]?:\/\/
Looks for either www or custom subdomain -> (?:www|[a-zA-Z0-9]+) -> www, evem, spot
Looks for at least 2 repetitions of a dot followed by some text -> (\.[a-zA-Z]+){2,} -> .gov.si
Looks for optional continuing relative path -> (.*(\/)?)* -> some/path/to/resource, foo/bar/, about/us.html
"""
full_url_regex = re.compile("^http[s]?:\/\/(?:www|[a-zA-Z0-9]+)(\.[a-zA-Z]+){2,}(.*(\/)?)*$")

"""
Matches if string is relative path format -> /path/to/resource.html
"""
relative_url_regex = re.compile("^(\/.*(\/)?)*$")

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
DEFAULT_DOMAIN_DELAY = 5  # seconds

# Resource types that will be blocked.
excluded_resource_types = ["image", "font", "media"]

image_extensions = ['.jpg', '.jpeg', '.jfif', '.pjpeg', '.pjp', '.png', '.apng', '.avif', '.gif', '.webp', '.svg',
                    '.eps', '.pdf', '.ico', '.cur', '.tif', '.tiff', '.bmp']
binary_file_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip']
binary_file_mime_dict = {
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
}
# Page timeout in milliseconds
PAGE_WAIT_TIMEOUT = 20000
