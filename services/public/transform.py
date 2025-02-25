import polars as pl

def parse_image_urls():

    schema = pl.Schema({
        'id': pl.String, 
        'data_updated_time': pl.String, 
        'presets': pl.List(pl.Struct({
            'data_updated_time': pl.String, 
            'history': pl.List(pl.Struct({
                'last_modified': pl.String, 
                'image_url': pl.String, 
                'size_bytes': pl.Int64})), 
            'id': pl.String
        }))
    })


    lf = pl.scan_ndjson("./data/stations/*.json", schema=schema)

    df = lf.collect()

    df = df.get_column("presets").explode().struct.field("history").explode().struct.unnest()


    df.get_column("image_url").to_frame().write_csv("image_urls.csv")

    return df


image_urls = parse_image_urls()

image_urls = image_urls.get_column("image_url").to_list()

print(image_urls)