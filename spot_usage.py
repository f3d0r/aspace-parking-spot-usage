import requests
import json
import csv

import pickle
import matplotlib.pyplot as plt

import numpy as np
from math import sin, cos, sqrt, atan2, radians, pi

""" url = "https://api.coord.co/v1/search/curbs/bybounds/all_rules"

# Make this a bounding box for whole city
querystring = {
    "min_latitude": "47.679981",
    "max_latitude": "47.678815",
    "min_longitude": "-122.395788",
    "max_longitude": "-122.393946",
    "access_key": "coord_api_key"
}
payload = ""
response = requests.request("GET", url, data = payload, params = querystring)
data = json.loads(response.text)
print(data)
quit() """

# Offloaded version.
with open('***REMOVED***', 'r') as content_file:
    content = content_file.read()
    data = json.loads(content)

print("Number of curb rules loaded in: ", len(data["features"]))

# Order data by curb_id.
counter = []
old_curb_id = data["features"][0]["properties"]["metadata"]["curb_id"]
for i in range(len(data["features"])):
    if data["features"][i]["properties"]["metadata"]["curb_id"]!=old_curb_id:
        counter.append(i)
    old_curb_id = data["features"][i]["properties"]["metadata"]["curb_id"]
counter.append(len(data["features"]))
data = [data["features"][counter[i]:counter[i+1]] for i in range(len(counter)-1)]


# Get curb lengths of allowed parking
curb_lengths = []   # indexed by curb_id in data
for i in data:
    allowed_parking_length = 0
    # Find allowed parking spots only:
    for j in i:
        if 'park' in j["properties"]["rules"][0]["permitted"] and j["properties"]["rules"][0]["vehicle_type"]=='all':
            try:
                allowed_parking_length += j["properties"]["metadata"]["distance_end_meters"] - j["properties"]["metadata"]["distance_start_meters"]
            except:
                allowed_parking_length += j["properties"]["metadata"]["distance_end_meters"]
    curb_lengths.append(allowed_parking_length)

# List of no park curbs:
unallowed_parking_curbs = [i for i in range(len(curb_lengths)) if curb_lengths[i]==0]
print("Number of curbs with no allowed parking: ", len(unallowed_parking_curbs))
data = [data[i] for i in range(len(data)) if i not in unallowed_parking_curbs]
print("Number of distinct curbs found: ", len(data))

# Remove these from curb_lengths now:
curb_lengths = [i for i in curb_lengths if i != 0]

PT = []
with open('ParkingTransaction.csv', newline='') as f:
    read = csv.reader(f)
    for row in read:
        PT.append(row)
PT = PT[1:]
meter_codes = []
for row in PT:
    meter_codes.append(row[1])

meter_codes = list(set(meter_codes))
meter_codes = [int(code) for code in meter_codes]
meter_codes = sorted(meter_codes)
meter_codes = [str(code) for code in meter_codes]
print("Number of meter codes obtained: ", len(meter_codes))

total_duration_by_meter = [0]*len(meter_codes)
last_row_code = PT[0][1]
ind = 0
for row in PT:
    if row[1]==last_row_code:
        total_duration_by_meter[ind] += int(row[7])
    else:
        ind += 1
    last_row_code = row[1]

PS = []
with open('Pay_Stations_Ordered.csv', newline='') as f:
    read = csv.reader(f)
    for row in read:
        PS.append(row)
PS = PS[1:]
meter_lng_lats = [None]*len(meter_codes)
cnt = 0
for i in range(len(meter_codes)):
    for j in range(cnt,len(PS)):
        if meter_codes[i]==PS[j][20]:
            meter_lng_lats[i] = PS[j][0:2]
            cnt += 1
            break

# Find indices of meter codes for which (lat,lng) could not be found:
a = [i for i in range(len(meter_lng_lats)) if meter_lng_lats[i]==None]
for i in range(len(a)):
    PT.pop(a[i]-i)
    meter_codes.pop(a[i]-i)
    meter_lng_lats.pop(a[i]-i)

print("Number of parking meters not matched to a coordinate: ", len(a))

# Get midpoints of curbs from coord's curb rules.
avg_curb_coords = []
for i in data:
    avg_curb_coords.append([i[0]["geometry"]["coordinates"][0][0]/2 + i[-1]["geometry"]["coordinates"][0][0]/2,
                            i[0]["geometry"]["coordinates"][0][1]/2 + i[-1]["geometry"]["coordinates"][0][1]/2])

# Approximate radius of earth in meters
R = 6373000.0
# Coord uses crowDistance!! Very close to their distance measurements between lng lat's
def crowDistance(lon1, lat1, lon2, lat2):
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance
# testing:
#print(4.62 - crowDistance(-122.32596423473412,47.61004406387254,-122.32591192499072, 47.610065944373275))

# Error likely in these functions. How to test and debug?
def toXY(coords):
    lng = pi*coords[0]/180
    lat = pi*coords[1]/180
    return [R*lng*cos(lat),R*lat]
# testing: IT'S WAY OFF OF COORD'S MEASUREMENTS, CROWDISTANCE IS RIGHT ON THO
c1 = toXY([-122.32596423473412, 47.61004406387254])
c2 = toXY([-122.32610904893714, 47.6099834899322])
print(sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2))
print(crowDistance(-122.32596423473412, 47.61004406387254, -122.32610904893714, 47.6099834899322))

# POSSIBLE NEW IDEA: INSTEAD OF toXY, USE crowDistance TO CONVERT
# TO A PLANAR GRID ON WHICH manhattanDistance IS COMPUTED
def manhattanDistance(curb_start, curb_end, meter_position):
    diff1 = curb_end[1]-curb_start[1]
    diff2 = curb_end[0]-curb_start[0]
    distance = abs(
        diff1*meter_position[0] - diff2*meter_position[1] +
        curb_end[0]*curb_start[1] - curb_end[1]*curb_start[0]
    ) / sqrt(diff1**2 + diff2**2)
    return distance

""" distances = [[] for i in meter_lng_lats]
for i in range(len(meter_lng_lats)):
    for j in range(len(avg_curb_coords)):
        # L2 norm on lat/lng coordinates method
        # distances[i].append(sqrt((float(meter_lng_lats[i][0])-j[0])**2 + (float(meter_lng_lats[i][1])-j[1])**2))

        # "Crow distance" method
        as_the_crow_flies = crowDistance(float(meter_lng_lats[i][0]), float(meter_lng_lats[i][1]), avg_curb_coords[j][0], avg_curb_coords[j][1])

        # Manhattan distance method
        if data[j][-1]["geometry"]["coordinates"][0]==data[j][0]["geometry"]["coordinates"][0]:
            manhattan_distance = manhattanDistance(
                    toXY(data[j][0]["geometry"]["coordinates"][0]), 
                    toXY(data[j][0]["geometry"]["coordinates"][1]),
                    toXY([float(meter_lng_lats[i][0]), float(meter_lng_lats[i][1])])
                )
        else:
            manhattan_distance = manhattanDistance(
                    toXY(data[j][0]["geometry"]["coordinates"][0]), 
                    toXY(data[j][-1]["geometry"]["coordinates"][1]),
                    toXY([float(meter_lng_lats[i][0]), float(meter_lng_lats[i][1])])
                )
  
        # Only accept if meter is near curb:
        if as_the_crow_flies < 40 and manhattan_distance < 5:
            distances[i].append((as_the_crow_flies, manhattan_distance))
        else:
            distances[i].append(None) """

with open("distances_pickled", "rb") as f:
            #pickle.dump(distances, f)
            distances = pickle.load(f)

print("length of distances: ", len(distances))
# The following structure is indexed in order of the meter_codes,
# and thus element i is the index of data with the closest curb_id 
# to meter `meter_codes[i]`!
closest_curb_indices = []
for i in distances:
    flag = True
    for j in i:
        if j!=None:
            closest_curb_indices.append(i.index(j))
            flag = False
            break
    if flag:
        closest_curb_indices.append(None)

print("length of closest curbs", len(closest_curb_indices))
# Are there curbs with many meters?
print("Number of meters matched to a curb that already has a match: ", 
       len([i for i in closest_curb_indices if i is not None]) - len(set([i for i in closest_curb_indices if i is not None])))

# Get denominators for weights (total possible parking time by curb)

# Seems like average parallel parking length for a car is 20-23 feet.
# Better to overestimate since people do not necessarily optimize
# space usage.
curb_car_capacity = []
for i in curb_lengths:
    curb_car_capacity.append(i/7) # divide by 7 meters (23 feet)

print("Curb lengths: ", curb_lengths[0:4])
print("Total parking durations: ", total_duration_by_meter[0:4])

# Assume people use parking from 7am to 7pm (total of 43200 seconds)
curb_time_capacity = [] # in seconds
                        # this is indexed by curb_id...
days = 1
for i in curb_car_capacity:
    curb_time_capacity.append(i*43200*days)

print("Curb time capacities: ", curb_time_capacity[0:3])

print("Maximum duration at a meter: ", max(total_duration_by_meter))

weight_by_meter = []
cnt = 0
for i in closest_curb_indices: # recall this is indexing essentially by meter_codes
    if i is not None:
        weight = total_duration_by_meter[cnt] / curb_time_capacity[i]
        weight_by_meter.append(weight)
    else:
        weight_by_meter.append(None)
    cnt += 1

print("Number of weights assigned to meters: ", sum(x is not None for x in weight_by_meter), cnt)
sorted_weights = sorted([i for i in weight_by_meter if i is not None])
#print("Maximum weights: ", sorted_weights)
print("720th value: ", sorted_weights[720])

weight_by_meter = [ x/sorted_weights[720] if x is not None else None for x in weight_by_meter ]

print("Number of parking meters matched to a curb: ", sum(x is not None for x in closest_curb_indices))
print(len(meter_codes))

closest_curbs = [data[i] if i is not None else None for i in closest_curb_indices]
parking_info = [meter_codes, meter_lng_lats, weight_by_meter, closest_curbs]
for i in parking_info:
    print(len(i))

### Basically need to parse coord data into parking data, then we'll be done integrating these weights

# Now we need to sum the parking durations of meters on the same curb 
# (assuming the parker is allowed to pay at either), and divide that by
# the total time that cars COULD be parked at that curb (which we'll 
# have to compute with an approximation for how much space a car takes
# when parallel parked; additionally, we'll need to factor in the conditional
# that the curb space CAN be parked at, and is not special-use).

plt.plot(list(range(len(sorted_weights))), sorted_weights)
plt.plot(list(range(len(sorted_weights))), [1]*len(sorted_weights),'--')
#plt.show()