
## Local server
start back-end application:
`./run-server-local.sh`
you might need to specify a project id explicitly:
`./run-server-local.sh --project_id PROJECTID`
Then you can access the server via http://localhost:5000
If you need to develop/debug front-end application start Angular server:  
`ng serve`
then you can access the server via http://localhost:4200
Angular application will forward api request to localhost:500 automatically
(thanks to proxy.conf.json)


## Running setup directly
Currently setup can be run from within application.
But previously it was only possible to by executing a script directly. 
And it's still possible.
```
export PYTHONPATH="."
python3 ./app/main.py "$@" --project_id PROJECTID --config config.json --service-account-key-file service_account.json
```
