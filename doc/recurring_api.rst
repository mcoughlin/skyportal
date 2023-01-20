
# Recurring Requests

There are circumstances where it may be useful to have API calls that repeat on a regular cadence. For example, ingesting nightly observations into SkyPortal is most convenient with such a cadence. For this reason, we have added the concept of recurring API calls into the application. These can be added using the ``recurring_api`` API endpoint, which takes the endpoint, method, time of the next call, and the delay between API calls. It also takes a dictionary payload corresponding to parameters to pass to the endpoint.


```
   data = {'endpoint' : 'observation/external_api',
           'method': 'post',
           'next_call': '2020-01-01T01:23:34',
           'call_delay': '1',
           'payload': {'allocation_id': 9}
          }
```
