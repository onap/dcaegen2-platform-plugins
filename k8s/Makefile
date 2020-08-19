build-wagon:
	@echo "### Copy generated k8s plugin"
	cp ../k8splugin-*.zip .

	@echo "### Create docker image (CentOS)"
	docker build -t k8splugin -f centos.wagon-builder.dockerfile .

	@echo "### Run docker container and generate wagon file"
	docker run -t --name k8s_container k8splugin:latest

	@echo "### Copy wagon file from docker image co current directory"
	docker cp k8s_container:/opt/app-root/src/output .

	@echo "### Remove docker container"
	docker rm k8s_container
