import os
import yaml
import click
from banal import keys_values

from followthemoney import model
from followthemoney.mapping.source import StreamSource
from followthemoney_util.cli import cli
from followthemoney_util.util import write_object


@cli.command('map', help="Execute a mapping file and emit objects")
@click.argument('mapping_yaml', type=click.Path(exists=True))
def run_mapping(mapping_yaml):
    config = load_config_file(mapping_yaml)
    stream = click.get_text_stream('stdout')
    try:
        for dataset, meta in config.items():
            for mapping in keys_values(meta, 'queries', 'query'):
                entities = model.map_entities(mapping, key_prefix=dataset)
                for entity in entities:
                    write_object(stream, entity)
    except BrokenPipeError:
        pass


@cli.command('map-csv', help="Map CSV data from stdin and emit objects")
@click.argument('mapping_yaml', type=click.Path(exists=True))
def stream_mapping(mapping_yaml):
    stdin = click.get_text_stream('stdin')
    stdout = click.get_text_stream('stdout')

    sources = []
    config = load_config_file(mapping_yaml)
    for dataset, meta in config.items():
        for data in keys_values(meta, 'queries', 'query'):
            query = model.make_mapping(data, key_prefix=dataset)
            source = StreamSource(query, data)
            sources.append(source)

    try:
        for record in StreamSource.read_csv(stdin):
            for source in sources:
                if source.check_filters(record):
                    entities = source.query.map(record)
                    for entity in entities.values():
                        write_object(stdout, entity)
    except BrokenPipeError:
        pass


def load_config_file(file_path):
    """Load a YAML (or JSON) bulk load mapping file."""
    file_path = os.path.abspath(file_path)
    with open(file_path, 'r') as fh:
        data = yaml.load(fh) or {}
    return resolve_includes(file_path, data)


def resolve_includes(file_path, data):
    """Handle include statements in the graph configuration file.

    This allows the YAML graph configuration to be broken into
    multiple smaller fragments that are easier to maintain."""
    if isinstance(data, (list, tuple, set)):
        data = [resolve_includes(file_path, i) for i in data]
    elif isinstance(data, dict):
        include_paths = data.pop('include', [])
        if not isinstance(include_paths, (list, tuple, set)):
            include_paths = [include_paths]
        for include_path in include_paths:
            dir_prefix = os.path.dirname(file_path)
            include_path = os.path.join(dir_prefix, include_path)
            data.update(load_config_file(include_path))
        for key, value in data.items():
            data[key] = resolve_includes(file_path, value)
    return data
