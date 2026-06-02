# FastAPI-XML

[![tests](https://github.com/cercide/fastapi-xml/actions/workflows/tests.yml/badge.svg)](https://github.com/cercide/fastapi-xml/actions)
[![codecov](https://codecov.io/gh/cercide/fastapi-xml/branch/master/graph/badge.svg)](https://app.codecov.io/gh/cercide/fastapi-xml)
[![license](https://img.shields.io/github/license/cercide/fastapi-xml)](https://github.com/cercide/fastapi-xml/blob/master/LICENSE)
[![versions](https://img.shields.io/pypi/pyversions/fastapi-xml.svg)](https://pypi.org/project/fastapi-xml/)

**Seamless XML support for FastAPI** — parse XML request bodies and return XML responses using standard Python dataclasses, with full OpenAPI integration.

```
pip install fastapi-xml
```

Built on [xsdata](https://github.com/tefra/xsdata) for XML serialization, it slots into FastAPI the same way JSON does.

## Features

- **XML request bodies** — replace `Body()` with `XmlBody()`, your endpoint receives a populated dataclass
- **XML responses** — return any dataclass and get back `application/xml` (or `text/xml`)
- **OpenAPI schema** — Swagger UI renders XML examples and schemas automatically
- **Zero learning curve** — works like FastAPI's JSON, just swap in `XmlRoute` and `XmlBody`
- **Two media types** — `XmlAppResponse` (`application/xml`) and `XmlTextResponse` (`text/xml`)

## Quick Start

```python
from dataclasses import dataclass, field
from fastapi import FastAPI
from fastapi_xml import XmlRoute, XmlAppResponse, XmlBody, add_openapi_extension

@dataclass
class HelloWorld:
    message: str = field(metadata={"type": "Element"})

app = FastAPI(title="FastAPI-XML", default_response_class=XmlAppResponse)
app.router.route_class = XmlRoute
add_openapi_extension(app)

@app.post("/echo", response_model=HelloWorld)
def echo(x: HelloWorld = XmlBody()) -> HelloWorld:
    x.message += " Forever!"
    return x
```

```xml
<!-- Request -->
<HelloWorld><message>Hello</message></HelloWorld>

<!-- Response -->
<HelloWorld><message>Hello Forever!</message></HelloWorld>
```

## How It Works

`XmlRoute` replaces FastAPI's default `APIRoute`. When a request arrives with an XML body, the `XmlDecoder` (wrapping xsdata's `XmlParser`) deserializes it into your dataclass. On the way out, `XmlResponse` serializes the return value back to XML via xsdata's `XmlSerializer`.

### Response Types

| Class            | `Content-Type`       |
|------------------|----------------------|
| `XmlAppResponse` | `application/xml`    |
| `XmlTextResponse`| `text/xml`           |

### OpenAPI

Call `add_openapi_extension(app)` to generate accurate XML schemas in your OpenAPI spec. The Swagger UI at `/docs` will show XML examples and let you test endpoints directly.

## Example

```python
from dataclasses import dataclass, field
from fastapi import FastAPI
from fastapi_xml import XmlRoute, XmlAppResponse, XmlBody


@dataclass
class Item:
    name: str = field(metadata={"type": "Element"})
    price: float = field(metadata={"type": "Element"})

@dataclass
class Order:
    id: str = field(metadata={"type": "Element"})
    items: list[Item] = field(metadata={"type": "Element", "name": "Item"})


app = FastAPI(default_response_class=XmlAppResponse)
app.router.route_class = XmlRoute


@app.post("/order", response_model=Order)
def create_order(order: Order = XmlBody()) -> Order:
    return order


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
```

## API

| Symbol               | Description                                   |
|----------------------|-----------------------------------------------|
| `XmlBody()`          | Mark a parameter as coming from XML body      |
| `XmlRoute`           | Route class that enables XML handling         |
| `XmlAppResponse`     | Response class for `application/xml`          |
| `XmlTextResponse`    | Response class for `text/xml`                 |
| `add_openapi_extension` | Patches OpenAPI schema for XML types       |

## Requirements

- Python 3.10+
- FastAPI >= 0.113.0
- xsdata >= 22.9

## License

MIT
