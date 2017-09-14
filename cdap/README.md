# cdap-cloudify
Contains a plugin and type file for deploying CDAP and related artifacts.

# service component name
When the cdap plugin deploys an application, it generates a service component name. That service component name is injected
into the node's runtime dictionary under the key "service_component_name" and also made available as an output under this key. 

# Demo blueprints
There is a subfolder in this repo called `demo_blueprints` that contains (templatized) example blueprints. 

# Connections
Since you cannot type-spec complicated objects in a cloudify node type, I have to explain this here. This is a requirement on all blueprints that use this node type. 

There is a property at the top level of the CDAP node called `connections` that is expecting a specific structure, best serviced with examples.

## DMaaP

### Message Router
Message router publication
```
      connections:
        streams_publishes:                      // is a list
          - name: topic00                       // THIS NAME MUST MATCH THE NODE NAME IN BLUEPRINT, SEE BELOW*
            location: mtc5
            client_role: XXXX
            type: message_router
            config_key:   "myconfigkey1"        // from spec
            aaf_username: { get_input: aafu1 }
            aaf_password: { get_input: aafp1 }
          - name: topic01                       // THIS NAME MUST MATCH THE NODE NAME IN BLUEPRINT, SEE BELOW*
            location: mtc5
            client_role: XXXX
            type: message_router
            config_key:   "myconfigkey2"        // from spec
            aaf_username: { get_input: aafu2 }
            aaf_password: { get_input: aafp2 }
```
Message router subscription is the exact same format, except change `streams_publishes` to `streams_subscribes`:
```
    streams_subscribes: 
          - name: topic00                        #MEANT FOR DEMO ONLY! Subscribing and publishing to same topic. Not real example.
            location: mtc5
            client_role: XXXX
            type: message_router
            config_key:   "myconfigkey2"
            aaf_username: { get_input: aafu2 }
            aaf_password: { get_input: aafp2 }
          - name: topic01
            location: mtc5
            client_role: XXXX
            type: message_router
            config_key:  "myconfigkey3"
            aaf_username: { get_input: aafu3 }
            aaf_password: { get_input: aafp3 }
```
The terms `streams_publishes` and `streams_subscribes` comes from the component specification. 

### Data Router
For publication, data router does not have the notion of AAF credentials, and there is no `client_role`. So the expected blueprint input is simpler than the MR case:
```
    streams_publishes:
     ...
     - name: feed00 
       location: mtc5
       type: data_router
       config_key: "mydrconfigkey"
```

Data router subscription is not supported because there is an impedance mistmatch between DR and CDAP.
CDAP streams expect a POST but DR outputs a PUT.
Some future platform capability needs to fill this hole; either something like the AF team's DR Sub or DMD. 

### Bound configuration
The above blueprint snippets will lead to the cdap application's `app_config` getting an entry that looks like this:
```
{  
   "streams_subscribes":{  
      "myconfigkey3":{  
         "type":"message_router",
         "aaf_username":"foo3",
         "aaf_password":"bar3",
         "dmaap_info":{  
            "client_role":"XXXX",
            "client_id":"XXXX",
            "location":"XXXX",
            "topic_url":"XXXX"
         }
      },
      "myconfigkey2":{  
         "type":"message_router",
         "aaf_username":"foo2",
         "aaf_password":"bar2",
         "dmaap_info":{  
            "client_role":"XXXX",
            "client_id":"XXXX",
            "location":"XXXX",
            "topic_url":"XXXX"
         }
      }
   },
   "streams_publishes":{  
      "myconfigkey1":{  
         "type":"message_router",
         "aaf_username":"foo1",
         "aaf_password":"bar1",
         "dmaap_info":{  
            "client_role":"XXXX",
            "client_id":"XXXX",
            "location":"XXXX",
            "topic_url":"XXXX"
         }
      },
      "mydrconfigkey":{  
         "type":"data_router",
         "dmaap_info":{  
            "username":"XXXX",
            "location":"XXXX",
            "publish_url":"XXXX",
            "publisher_id":"XXXX",
            "log_url":"XXXX",
            "password":"XXXX"
         }
      },
      "myconfigkey0":{  
         "type":"message_router",
         "aaf_username":"foo0",
         "aaf_password":"bar0",
         "dmaap_info":{  
            "client_role":"XXXX",
            "client_id":"XXXX",
            "location":"XXXX",
            "topic_url":"XXXX"
         }
      }
   }
}
```
## HTTP
In addition to DMaaP, we support  HTTP services.

### Services Calls
In a blueprint, to express that one component calls asynchronous HTTP service of another component, writing this as `A -> B,` you need:

1. `A` to have a `connections/services_calls` entry:
```
    connections:
      services_calls:
        - service_component_type: laika
          config_key: "laika_handle"
```
2. A relationship of type `dcae.relationships.component_connected_to` from A to B.

3. The `B` node's `service_component_type` should match #1

See the demo blueprint `cdap_hello_world_with_laika.yaml`

### Bound Configuration

The above (without having defined streams) will lead to:
```
{  
   "streams_subscribes":{  

   },
   "streams_publishes":{  

   },
   "services_calls":{  
      "laika_handle":[  
         "some_up:some_port"
      ]
   }
}
```
Note that the value is always a list of IP:Ports because there could be multiple identical services that satisfy the client (A in this case). This is client side load balancing. 

# Tests
To run the tests, you need `tox`. You can get it with `pip install tox`. After that, simply run `tox -c tox-local.ini` from inside the `cdapplugin` directory to run the tests and generate a coverage report.
