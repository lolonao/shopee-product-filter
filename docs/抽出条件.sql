-- 条件を満たす商品
SELECT
  price,
  sold,
  shop_type,
  product_name,
  product_url,
  image_url
FROM
  productbasicitems
WHERE
  price >= 26 AND price <= 267 AND
  sold >= 3 AND sold <= 100;

SELECT price, sold, shop_type, product_name, product_url, image_url FROM productbasicitems WHERE price >= 26 AND price <= 267 AND sold >= 3 AND sold <= 100;





-- 全権抽出
SELECT
  price,
  sold,
  shop_type,
  product_name,
  product_url,
  image_url
FROM
  product_basic_items
