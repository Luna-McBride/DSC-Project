##
from flask import Flask, request, Response, jsonify
import jsonpickle
from PIL import Image
import platform
import io, os, sys
import pika
import hashlib, requests
import json
from google.cloud import bigquery
import pandas as pd

import matplotlib
import matplotlib.pylab as plt
matplotlib.rcParams['interactive'] == True

matplotlib.use(plt.get_backend())

# Initialize the Flask application
app = Flask(__name__)

##
## Configure test vs. production
##

rabbitMQHost = os.getenv("$RABBITMQ_HOST") or "localhost"


print("Connecting to rabbitmq({})".format(rabbitMQHost))

##
## Your code goes here..
##
REST = os.getenv("rest") or "localhost:5000"

bqClient = bigquery.Client(project = "project-datacenter-computing")
dataId = "project-datacenter-computing.weatherData"

fields = ["tempmax","tempmin","dew","snow","humidity","precip","windspeed","uvindex"] #Get the list of determined fields.
#conditions was removed from the fields to be chosen as that was only needed in the cleanup.

#PullData: Pulls weather data from the API
#Input: the city via JSON request
#Output: a JSON response saying that it is queued to happen
@app.route("/api/pullData", methods = ["POST"])
def pullData():
    #Build the rabbit connection
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbitMQHost))
    channel = connection.channel() #Open the rabbit channel

    channel.queue_declare(queue='task_queue') #Declare the queue

    req = request #Get the request
    jsonData = json.loads(req.data) #Load the passed in data
    cities = jsonData["city"] #Get the city/cities passed in

    #If the request is multiple cities, do the publish for each one
    if type(cities) == list:

        #For each city, publish the city request to the queue
        for city in cities:
            #Publish the city to be processed to Rabbit
            channel.basic_publish(
                exchange='',
                routing_key='task_queue',
                body = city)
            print(" [x] Sent %r" % city) #Print that it was sent to the worker
    #If only one city was sent
    else:
        #Sent the request for the one city
        channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body = cities)
        print(" [x] Sent %r" % cities) #Print that the request was sent
    
    connection.close() #Close the rabbit connection

    #Return a response saying that the action was queued
    return Response(response=json.dumps({"Action" : "Queued"}), status=200, mimetype="application/json")

 
#getAll: Gets all of the data from the database of the specified type
#Input: the specified type, sent via the url
#Output: a response to send to the client
@app.route("/api/getAll", methods = ["GET"])
def getAll():
    #Build a query to get the table names
    query = '''SELECT
        table_name
        FROM
            project-datacenter-computing.weatherData.INFORMATION_SCHEMA.TABLES'''

    result = list(bqClient.query(query).to_dataframe()["table_name"]) #Put the received table names into a list
    print(result) #Print out the table list
    
    #Return a response with the table list
    return Response(response = json.dumps({"Tables" : result}), status = 200, mimetype = "application/json")

#DeleteCity: deletes a city table from the database
#Input: City via JSON in HTML request
#Output: A response saying that the city is gone
@app.route("/api/deleteCity", methods = ["GET"])
def deleteCity():
    req = request #Get the request
    jsonData = json.loads(req.data) #Load the passed in data
    cities = jsonData["city"] #Get the cities

    bqClient.delete_table(dataId + "." + cities, not_found_ok=True) #Delete the city as per https://cloud.google.com/bigquery/docs/samples/bigquery-delete-table

    #Build a query to get the table names
    query = '''SELECT
        table_name
        FROM
            project-datacenter-computing.weatherData.INFORMATION_SCHEMA.TABLES'''

    result = list(bqClient.query(query).to_dataframe()["table_name"]) #Put the received table names into a list
    print("Current tables: {}".format(result)) #Print out the table list

    #Return a response saying that the city is gone
    return Response(response = json.dumps({"Deleted" : cities}), status = 200, mimetype = "application/json")

#PlotData: Puts the two cities' data into one plot
#Input: The two dataframes and city names
#Output: A single combined plot
def plotData(result1, result2, city1, city2):
    result1["datetime"] = pd.to_datetime(result1["datetime"]) #Put the datetime field into an actual datetime
    result2["datetime"] = pd.to_datetime(result2["datetime"]) #Put the datetime field into an actual datetime

    result1 = result1.set_index("datetime") #Set the date as the index
    result2 = result2.set_index("datetime") #Set the date as the index

    result1Col = result1.columns #Get the column names
    colName = result1Col[0] #Get the variable name, as that could be one of a few
    result1[city1 + colName] = result1[colName] #Set a new column that shows the city name for plotting
    result1 = result1.drop(colName, axis = 1) #Drop the original

    result2Col = result2.columns #Get the column names
    colName2 = result2Col[0] #Get the variable name, as that could be one of a few
    result2[city2 + colName2] = result2[colName2] #Set a new column that shows the city name for plotting
    result2 = result2.drop(colName2, axis = 1) #Drop the original

    ax = result1.plot(title = colName + " " + city1 + " VS " + city2) #Plot the first dataframe
    result2.plot(ax = ax) #Plot the second on the same plot

    plt.plot() #Force the plot to plot
    plt.show() #Display the plot

    #The rest follows this StackOverflow answer to store the plot image: https://stackoverflow.com/questions/57369606/python-plotting-api-how-to-expose-your-scientific-python-plots-through-a-flask

    bytes_image = io.BytesIO() #Put the image into bytes
    plt.savefig(bytes_image, format='png') #Save the figure
    bytes_image.seek(0) #Seek back to the origin of the file
    return bytes_image #Return the image

#GetPlot: Creates a plot for a specified field for a specified city
#Input: 2 cities and the specified field, pulled in by the JSON request
#Output: A graph image
@app.route("/api/getPlot", methods = ["GET"])
def getPlot():
    req = request #Get the request
    jsonData = json.loads(req.data) #Load the passed in data
    cities = jsonData["city"] #Get the cities
    field = jsonData["field"] #Get the specified field
    notLoaded = 0 #Holder variable to see if both cities are loaded

    #Build a query to get the table names
    query = '''SELECT
        table_name
        FROM
            project-datacenter-computing.weatherData.INFORMATION_SCHEMA.TABLES'''

    result = list(bqClient.query(query).to_dataframe()["table_name"]) #Put the received table names into a list
    print(result) #Print out the table list
    
    #If the given field is not in the list, send an error
    if not field in fields:
        #Send an error with the usable fields
        return Response(response = json.dumps({"Error" : "Please choose from these fields: {}".format(fields)}), status = 403, mimetype = "application/json")
    
    nonLoaded = [] #Build a variable to show that a city is not loaded
    #For each city, make sure it is loaded in the database
    for city in cities:
        #If the city is not loaded into the database, change the notLoaded variable to 1
        if city not in result:
            notLoaded = 1 #Show that something is not loaded
            nonLoaded.append(city) #Add the city to the nonLoaded variable
    
    #If there is a city not loaded, tell the user to load it
    if notLoaded != 0:
        #Send a response to say a city is not loaded
        return Response(response = json.dumps({"Error" : "The city/cities {} are not loaded. Use pullData to load it".format(nonLoaded)}), status = 403, mimetype = "application/json")

    #Use a query to get the specified field for the specified city
    query1 = '''SELECT datetime, {} FROM project-datacenter-computing.weatherData.{}'''.format(field, cities[0])
    query2 = '''SELECT datetime, {} FROM project-datacenter-computing.weatherData.{}'''.format(field, cities[1])

    #Run the queries and convert them into dataframes
    result1 = bqClient.query(query1).to_dataframe()
    result2 = bqClient.query(query2).to_dataframe()

    #Print them to the rest for my sake
    print(result1.head())
    print(result2.head())

    img = plotData(result1, result2, cities[0], cities[1]) #Plot the data in the plotData function
    imgPickle = jsonpickle.encode(img) #Encode the resulting image with JSON pickle
    return Response(imgPickle, status = 200, mimetype='image/png') #Return a response with the image

# start flask app
app.run(host="0.0.0.0", port=5000)