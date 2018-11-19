Welcome to Nudnik
=================

Goal
----------------

Allow easy testing of load-balancing and failures in gRPC and REST based service-mesh

Features
----------------

 - Rate limiting
 - 

Deploy
----------------

 * Clone and initialize Nudnik:
```shell
pip install grpcio grpcio-tools                          
git clone https://github.com/salosh/nudnik.git
git config --global push.default matching
git config --global user.name "Your Name"
git config --global user.email your.email@salosh.org
cd nudnik
python -m grpc_tools.protoc --proto_path=. ./entity.proto --python_out=. --grpc_python_out=.
```

 * Configure:
Via flags:
```shell
./nudnik.py -h
```
Via config file:
```shell  
nano ./config.yml     
```

 * Run example Server:
```shell
./nudnik.py --server
```

 * Run example Client:
```shell
./nudnik.py --streams 20 --mps 5 --name foobar
```

* * *
Visit our website at https://salosh.org
