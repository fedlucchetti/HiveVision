# vision

The goal is to provide an API service that is ready to deploy on an almost fresh VM, ssh, firewall, user config, excepted for now. Ansible deploys the webapp to the server, and launches the containers via docker-compose. Routes provided are experimental for now as development was focused on the deployment and running of the service itself.

Architecture:
Docker containers serve a flask app through gunicorn, reverse proxied with nginx on port 80. The flaskapp provides a number of GET and POST routes and has persistent memory through a redis db and mongodb. The flask app also implements an image queue.

- deploy: this folder contains an ansible playbook to deploy and launch the service on a fresh VM. At       this stage, the VM cannot be absolutely fresh, security and users need to be configured.
- app: contains the actual server logic, with additional functional python modules
- nginx: contains the files for the reverse proxy configured nginx sitting in front of gunicorn
- docker_compose.yml: this is central to docker's tools and needs to be referenced by docker-compose when start/stopping.


## deployment
Use this to deploy from within the /deploy folder to a remote machine:
```
ansible-playbook deploy_book.yml -u USER
```
