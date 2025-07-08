
"__tablename__" overrides symbol of same name in class "SQLModel"..
__tablename__: str = TABLE_NAME_PRODUCT_LIST 


"get_product_list_session" is not defined..
ProductListSession = Annotated[Session, Depends(get_product_list_session)]

undefined ..
with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="wb") as tmp:

その他多数の警告

    if min_price_sgd is not None: statement = statement.where(ProductBasicItem.price >= min_price_sgd)
    if max_price_sgd is not None: statement = statement.where(ProductBasicItem.price <= max_price_sgd)
    if min_sold is not None: statement = statement.where(ProductBasicItem.sold >= min_sold)
    if max_sold is not None: statement = statement.where(ProductBasicItem.sold <= max_sold)
 

    statement = statement.offset(offset).limit(limit).order_by(ProductBasicItem.id)

ちゃんとpython 3.12.10 にあわせて修正して。


---

__tablename__ = TABLE_NAME_PRODUCT_LIST
Type "Literal['product_basic_items']" is not assignable to declared type "declared_attr[Unknown]" ...

 
The method "utcnow" in class "datetime" ...
created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

Tte method "on_event" in class "FastAPI" is deprecated
@product_list_app.on_event("startup")
