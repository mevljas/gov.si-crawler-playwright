import threading

# A set with domains next available times.
domain_available_times = {}
# A set with ip next available times.
ip_available_times = {}
# Lock for accessing  domain_available_times and ip_available_times by multiple threads.
lock = threading.Lock()
# Remember for each thread whether is sleeping (False) or running (True).
threads_status = {}
