NAME = backend
URL = docker.sinacomsys.local/devops/developer-dashboard

all:
	docker buildx build -t $(URL)/$(NAME) .
