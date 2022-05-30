# Is usually a good idea to split our business model data into Read Data (Views) and
# Write Data (Models). This calls for a need of mantain two paralell services in order
# to better synchronize our data.

from wintry.ioc import provider

# Write your view services providers here