# ieps-assignment-1
A standalone crawler that crawls only .gov.si web sites. 

## Project setup

### Setup environment variables
```bash
cp .env.example .env
```
Edit **.env** file if necesarry.

### Run Docker Postgres database

```bash
docker-compose up -d
```

### Create and use virtual env
```bash
pip install virtualenv
python<version> -m venv <virtual-environment-name>
source env/bin/activate
```

Alternatively you can set up it using Pycharm.
### Install requirements

```bash
pip install -r requirements.txt
```

### Run database migrations
```bash
python migrate.py
```

## Run the crawler
```bash
python main.py
```
