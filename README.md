# Datacenter-Scale Computing Final Project: Weather Data Comparison

![Example](https://github.com/Luna-McBride/DSC-Project/blob/main/loadImage.jpg)

This is the final personal project for the Datacenter-Scale Computing class at CU Boulder (CSCI 5253). The project utilizes the Visual Crossing Weather API, BigQuery, RabbitMQ, and the Google CLoud Platform's Kubernetes Engine to compare in one quick and convinient place. The original idea for this project came from how hard I was finding it to compare weather between cities. Weather is one of the most important things to me when it it comes to contemplating places to visit/move to in the future. It is surprisingly difficult to find data beyond the regular week at a glance, and the places that have more generalized data have so much clutter that it is hard to set two cities up for a real comparison. 

The end result in this case is documented in the diagram and explanation below. Note that I did not have the time to finish the final step of getting the worker and server pods up into the Kubernetes Engine.

![Diagram](https://github.com/Luna-McBride/DSC-Project/blob/main/Project-Diagram.drawio%20(1).png)

This function works as an API with 4 main API calls: add cities to the BigQuery database, delete a city from the database, show the cities in the database, and a graphing function. 

* The adding function "pullData" works by doing an API call to the Visual Crossing API for 2 segments of 6 months, cleans up the snow column, combines the two sets, and adds them to BigQuery. This had to be done this way due to the limits on singular requests that the Visual Crossing API has. This may be the longest portion, so it sends it to the worker via RabbitMQ to try and hide this time from the user.

* The delete function "deleteCity" simply deletes the specified table using bigqueryClient.delete_table then shows what still exists, as well as the deleted table's name.

* The show cities function "getAll" gets the table names from the database and shows them.

* The graphing function "getPlot" first checks and makes sure that the given cities are in the database and the desired field does exist (such as the max temperature, called tempmax). It then queries the database for the associated cities and sends it to the "plotData" function, which plots the data and sends back the plot image in the form of bytes. This gets sent all the way back as seen in the example max temperature image.

This project is limited compared to initial plans. I originally hoped for the data to be in 5-year averages, but the weather api limits made that unfeasible. This api also has a misleading pricing structure, where the price form says it is per request. In reality, each individual bit of data is counted as one. The base output without specifying columns is full of random fields like sunrise time and moon phase. These filled up the free daily request count fill up very fast. Yet, despite all of these complaints, this was still better than the other weather API's I tried before this one. In the end it did exactly what I needed to and contained non-US cities like Sendai, hence why I chose it.
