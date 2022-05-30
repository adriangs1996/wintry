from wintry.settings import TransporterType

settings = {
    # Full Configuration section for Winter Settings.
    # backends configures your data sources. You can use them to
    # configure a MongoDB, a Postgres, SQLite, ElasticSearch, etc,
    # anything you need. Defaults to sqlite with asyncio support.
    # You can provide more than one backend in here, but ensure
    # you specify a correct driver and a name for that backend.
    "backends": [
        # BackendOptions object
        {
            # Name which will make this driver accessible to the framework.
            # Leaving "default" if only one backend is used, is usefull as
            # you wont need to specify the name on each backend action.
            "name": "default",

            # "driver" Must be an importable path to a backend driver.
            # Drivers should provide a "factory" function which will
            # be called to get a driver instance. This driver is then
            # attached to the backend and is in charge to process the repositories
            # queries, so it most implement the QueryDriver interface for its
            # data source.
            "driver": "wintry.drivers.pg",
            
            # ConectionOption objects provide a lot of properties to configure
            # the conection to your data source. Nonetheless, is adviced to only
            # use the "url" (if possible) as most systems considered it enough
            # for a successfull connection.
            "connection_options": {"url": "sqlite+aiosqlite:///sqlite.db"},
        },

        # If needed, replicate the object structure above and add more backends
        # here

    ],

    # Auto discovery is triggered by the "snowman" cli and at server startup
    # to register your models, repositories, configure dependency injection
    # and more. If you plan to fully control your imports, then disable this
    # and manually register your components
    "auto_discovery_enabled": True,
    
    # Enabled metadata creation at server startup. This ease development as there
    # is no need to start migrations on the begining of the project. If you are not
    # going to use metadata (e.g your system does not perform migrations because
    # it is using MongoDB, etc) you can turn this off.
    "ensure_metadata": True,

    # "modules" pairs with auto_discovery_enabled flag to configure the 
    # autodiscovery functionality. This should be a list directories
    # where wintry will look for modules to import for you. 
    "modules": [
        "apps/contrib",
        "apps/{{cookiecutter.project_name}}",
    ],

    # Install a middleware in your server. By default, it provides
    # a CORS middleware which allows for any source to communicate.
    # This ease development by it is not a production ready config.
    "middlewares": [
        {
            # The name of the callable that implements a particular middleware. 
            "name": "CORSMiddleware",

            # An importable path to the middleware module that contains the middleware
            # callable.
            "module": "fastapi.middleware.cors",

            # Arguments to pass to the middleware at creation time.
            # Should be in **kwargs** format
            "args": {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
        }
    ],

    # Transporters are used for external comunication.
    # You can use them to listen for outside events, like
    # a Redis broker or a RabbitMQ server.
    "transporters": [
        # {
        #     # The transporter type to use.
        #     "transporter": TransporterType.redis,
        
        #     # An importable path to the transporter implementation
        #     # module
        #     "driver": "wintry.transporters.redis",
        
        #     # The name of the class implementing the transporter
        #     # in module
        #     "service": "RedisMicroservice",
        #     "connection_options": {
        #         "url": "redis://localhost"
        #     }
        # }
    ],
    "sever_title": "{{cookiecutter.project_name}}",
    "server_prefix": "",
    "server_version": "0.0.1",
    "include_error_handling": True,
    "host": "0.0.0.0",
    "hot_reload": True,
    "port": 8000,
    "excluded_folders": [],
    "app_path": "server:app",
}
