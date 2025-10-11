https://pimylifeup.com/raspberry-pi-docker/

# install docker

curl -sSL https://get.docker.com | sh

logout

type in id to get id and gid and update .env

sudo usermod -aG docker $USER

and re-login

so you can run docker compose without sudo.
