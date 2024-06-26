# FastAPI::XML

![tests](https://github.com/cercide/fastapi-xml/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/cercide/fastapi-xml/branch/master/graph/badge.svg)](https://app.codecov.io/gh/cercide/fastapi-xml)
![license](https://img.shields.io/github/license/cercide/fastapi-xml)
[![CodeFactor](https://www.codefactor.io/repository/github/cercide/fastapi-xml/badge)](https://www.codefactor.io/repository/github/cercide/fastapi-xml)
![versions](https://img.shields.io/pypi/pyversions/fastapi-xml.svg)

`pip install fastapi-xml`


A bridge between [FastAPI](https://github.com/tiangolo/fastapi) and [xsdata](https://github.com/tefra/xsdata). Together,
fastapi handles xml data structures using dataclasses generated by xsdata. Whilst, fastapi handles the api calls, xsdata
covers xml serialisation and deserialization. In addition, openapi support works as well.

![Swagger Example](https://github.com/cercide/fastapi-xml/raw/master/.github/rsc/example.png)

```python
from dataclasses import dataclass, field
from fastapi import FastAPI
from fastapi_xml import add_openapi_extension
from fastapi_xml import XmlRoute
from fastapi_xml import XmlAppResponse
from fastapi_xml import XmlBody

@dataclass
class HelloWorld:
    message: str = field(metadata={"examples": ["Foo"],"name": "Message", "type": "Element"})

app = FastAPI(title="FastAPI::XML", default_response_class=XmlAppResponse)
app.router.route_class = XmlRoute
add_openapi_extension(app)

@app.post("/echo", response_model=HelloWorld, tags=["Example"])
def echo(x: HelloWorld = XmlBody()) -> HelloWorld:
    x.message += " For ever!"
    return x

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```
