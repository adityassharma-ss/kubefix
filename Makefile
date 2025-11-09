.PHONY: build run test deploy

VERSION=v1.0.0
IMAGE=kubefix
NAMESPACE=kubefix

build:
	docker build -t $(IMAGE):$(VERSION) .

run:
	docker-compose up -d

test:
	docker-compose run --rm kubefix pytest src/tests

deploy:
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/rbac.yaml
	kubectl apply -f k8s/secrets.yaml
	kubectl apply -f k8s/deployment.yaml

clean:
	docker-compose down -v
	docker rmi $(IMAGE):$(VERSION)

.env:
	cp .env.template .env