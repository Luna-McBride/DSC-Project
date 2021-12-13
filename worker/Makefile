VERSION=v1
DOCKERUSER=lunarreign

build:
	docker build -f Dockerfile-worker -t weather-worker .
push:
	docker tag weather-worker $(DOCKERUSER)/weather-worker:$(VERSION)
	docker push $(DOCKERUSER)/weather-worker:$(VERSION)
	docker tag weather-worker $(DOCKERUSER)/weather-worker:latest
	docker push $(DOCKERUSER)/weather-worker:latest

##
## The dirkcgrunwald/flair:latest container simply includes the FLAIR library
##

DOCKERUSER_FLAIR=dirkcgrunwald
build-base:
	docker build -f Dockerfile-flair -t flair .
push-base:
	docker tag flair $(DOCKERUSER_FLAIR)/flair:latest
	docker push $(DOCKERUSER_FLAIR)/flair:latest