# toys.micahrl.com

Deploy with a swarm, using a registry on the swarm

    docker swarm init
    docker service create --name registry -p 5000:5000 registry:2

    docker build -t localhost:5000/toys-frontend:latest .
    pushd ~/biblemunger && docker build -t localhost:5000/biblemunger:latest && popd

    docker stack deploy --compmose-file docker-compose.yml toys
