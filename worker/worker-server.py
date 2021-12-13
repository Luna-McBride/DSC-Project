#
# Worker server
#
import pickle
import platform
import io
import os
import sys
import pika
from google.cloud import bigquery
import hashlib
import json
import requests
import time
import pandas as pd

import sys
from configparser import ConfigParser 

import urllib.parse
import urllib.request


hostname = platform.node()

##
## Configure test vs. production
##

rabbitMQHost = os.getenv("$RABBITMQ_HOST") or "localhost"

print(f"Connecting to rabbitmq({rabbitMQHost})")

parser = ConfigParser() #Start up the parser
path = sys.path[0] #Get the path to this point
path = path + "/secrets.txt"  #Add in the file, with two extensions since I can never have nice things

parser.read_file(open(path, "r")) #Open the file for the parser
apiKey = parser.get("weather", "key") #Get the API Key
 

bqClient = bigquery.Client(project = "project-datacenter-computing") #Create the bigquery client

tableId = "project-datacenter-computing.weatherData" #Set up the table id

#Try to create a new dataset if needed. Otherwise, say it is already there
try:
    dataset = bigquery.Dataset(tableId) #Create a dataset variable
    dataset = bqClient.create_dataset(dataset, timeout=30) #Create the dataset

#If the dataset is already there
except Exception as e:
    print(e) #Print the error
    print("The dataset is already created") #Say that it is already there



#Following the documentation in the weather api
#https://www.visualcrossing.com/resources/documentation/weather-api/how-to-load-weather-data-into-a-juypter-notebook/

#PullData: pulls the weather for the given city, limited to 1 year because of limitations of the api
#Input: the city
#Output: two separate json loads for separate 6-month request, as any more goes past the api's limitations
def pullData(city):
    #Request the most recent 6 months from June 2021 until now
    requestUrl = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{}".format(city)
    requestUrl = requestUrl+ "/2021-06-10/2021-12-10"+"?key="+ apiKey +"&include=obs"
    requestUrl = requestUrl + "&elements=datetime,tempmax,tempmin,dew,snow,humidity,precip,windspeed,conditions,uvindex"
    
    #Request the 6 months previous to June 2021
    requestUrl2 = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{}".format(city)
    requestUrl2 = requestUrl2+ "/2020-12-10/2021-06-09"+"?key="+ apiKey +"&include=obs"
    requestUrl2 = requestUrl2 + "&elements=datetime,tempmax,tempmin,dew,snow,humidity,precip,windspeed,conditions,uvindex"
         
    print('Weather requestUrl={requestUrl}'.format(requestUrl=requestUrl)) #Print one of the fields

    #Try to open the two requests
    try:
        req = urllib.request.urlopen(requestUrl) #Open the first 6 months
        req2 = urllib.request.urlopen(requestUrl2) #Open the last 6 months
    
    #If the two cannot open, show the exception
    except Exception as e:
        print(e) #Print the exception
        print("Could not read from:"+requestUrl) #Give a generic message
        return [] #Exit
                
    rawForecastData = req.read() #Read from the first request
    rawForecastData2 = req2.read() #Read from the second request
    
    #Close the requests
    req.close()
    req2.close()
    return [json.loads(rawForecastData), json.loads(rawForecastData2)] #Return the requests

#Source for json_normalize: https://stackoverflow.com/questions/21104592/json-to-pandas-dataframe

#ProcessData: convert the two 6-month json files into one pandas dataframe, plus some cleaning
#Input: The two json files containing 6 months of data
#Output: the clean, combined dataset
def processData(first6, last6):
    first = first6["days"] #Get only the days section out of the json
    last = last6["days"] #As that contains the actual weather data
    
    firstDf = pd.json_normalize(first) #Normalize the json into pandas form
    lastDf = pd.json_normalize(last) #For both 6 month variants contained
    yearDf = pd.concat([lastDf, firstDf]) #Concat to form a single dataset
    
    #It appears that the only field that can truly be null is snow. In fact, it is entirely null
    #The amount of snow would be the precipitation on days where conditions has snow. Thus, that is how I will fill it
    #print(yearDf["conditions"].unique()) #These two exist just for the above note
    #print(yearDf.loc[yearDf["snow"].notnull()])
    
    #Adjust the snow field into something that can actually be worked with
    yearDf["snow"] = yearDf.apply(lambda x: 0 if "Snow" not in x["conditions"] else x["precip"], axis = 1)
    
    return yearDf #Return the processed dataset

#Build the rabbit connection
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=rabbitMQHost))
channel = connection.channel() #Create a channel for the connection

channel.queue_declare(queue='task_queue') #Declare the queue
print(' [*] Waiting for messages. To exit press CTRL+C') #Print that it is waiting for input

#Callback: Handles callback functionality for rabbit, as well as dataset creation and cleaning
#Input: the channel, the method, some properites, and the actual city being passed in
#Output: An acknowledgement to the queue
def callback(ch, method, properties, body):
    city = body.decode() #Decode the city name from the body
    print(" [x] Received %r" % city) #Print that it has been received

    time.sleep(body.count(b'.')) #Do a quick sleep

    #Do a quick query to get the table name as per https://cloud.google.com/bigquery/docs/quickstarts/quickstart-client-libraries#client-libraries-install-python
    query = '''SELECT
        table_name
        FROM
            project-datacenter-computing.weatherData.INFORMATION_SCHEMA.TABLES'''

    datasets = list(bqClient.query(query).to_dataframe()["table_name"]) #Put the table names (previous cities) into a list

    #If the city has not been processed, process the city
    if not city in datasets:
        [first6, last6] = pullData(city) #Pull the first and last 6 months to create a whole year (api limits would not let me do more)
        yearDf = processData(first6, last6) #Combine them and clean them up

        newTable = tableId + "." + city #Create a new table name from the city
        job = bqClient.load_table_from_dataframe(yearDf, newTable) #Put that city into the database

        job.result() #Show results

    #If the city has already been processed
    else:
        print("This is already loaded") #Print that is has already been loaded
    
    print(" [x] Done") #Print that it is done
    ch.basic_ack(delivery_tag = method.delivery_tag) #Send the acknowledgement to the channel


channel.basic_qos(prefetch_count=1) 
channel.basic_consume(queue='task_queue', on_message_callback=callback) #Build the consume queue

channel.start_consuming() #Start consuming