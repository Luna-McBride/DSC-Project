VERSION=v1
DOCKERUSER=lunarreign

build:
	docker build -f Dockerfile-rest -t weather-rest .

push:
	docker tag weather-rest $(DOCKERUSER)/weather-rest:$(VERSION)
	docker push $(DOCKERUSER)/weather-rest:$(VERSION)
	docker tag weather-rest $(DOCKERUSER)/weather-rest:latest
	docker push $(DOCKERUSER)/weather-rest:latest
