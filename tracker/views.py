"""
views.py

URL route handlers

Note that any handler params must match the URL route params.
For example the *say_hello* handler, handling the URL route '/hello/<username>',
  must be passed *username* as the argument.

"""

from flask import request, Response, abort
from pykml import parser
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError
from google.appengine.ext.db import BadValueError
import urllib2
import time
import json
import logging
import delorme

from tracker import app

from models import Point, Tracker

@app.errorhandler(404)
def page_not_found(e):
	"""Return a custom 404 error."""
	return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def page_not_found(e):
	"""Return a custom 500 error."""
	return 'Sorry, unexpected error: {}'.format(e), 500


@app.route("/_ah/warmup")
def warmup():
	return ''

@app.route('/api/v1/point/route/load', methods=['POST'])
def load_route():
    try:
        data = json.loads(request.data)
        url = data['url']
    except Exception as e:
        logging.error(e.args[0])
        abort(400)

    obj = urllib2.urlopen(url)
    str = obj.read()
    kml_str = ""
    for line in iter(str.splitlines()):
        if not 'atom:link' in line:
            kml_str+=line
            kml_str+='\n'

    Point.delete_all('route')

    root = parser.fromstring(kml_str)

    pointid = 0
    for placemark in root.Document.Folder.Placemark:
        coordinates = placemark.MultiGeometry.Point.coordinates.text.split(',')
        try:
            point = Point(
                title = placemark.name.text,
                type = 'route',
                latitude = float(coordinates[1]),
                longitude = float(coordinates[0]),
                pointid = pointid
            )
        except TypeError:
            abort(500)
        except Exception as e:
            logging.error(e.args[0])
            abort(500)
        try:
            point.put()
        except CapabilityDisabledError:
            logging.error(u'App Engine Datastore is currently in read-only mode.')
            abort(500)
        except Exception as e:
            logging.error(e.args[0])
            abort(500)

        pointid += 1

    return list_point('route')

@app.route('/api/v1/point/<type>', methods=['GET'])
def list_point(type):
    points_dict = []
    points = Point.query(Point.type == type).order(Point.timestamp, Point.pointid).fetch()
    for point in points:
        points_dict.append(point.to_dict())

    return Response(json.dumps(points_dict), mimetype='application/json');


@app.route('/api/v1/point/<type>/<id>', methods=['GET'])
def get_point(type, id):
    point = Point.get_by_id(int(id))
    return Response(json.dumps(point.to_dict()), mimetype='application/json');


@app.route('/api/v1/point/<type>/<id>', methods=['PUT'])
def update_point(type, id):
    point = Point.get_by_id(int(id))
    data = json.loads(request.data)
    point.title = data['title']
    point.latitude = data['latitude']
    point.longitude = data['longitude']
    try:
        point.put()
    except CapabilityDisabledError:
        logging.error(u'App Engine Datastore is currently in read-only mode.')
        abort(500)
    except Exception as e:
        logging.error(e.args[0])
        abort(500)

    return Response(json.dumps(point.to_dict()), mimetype='application/json');


@app.route('/api/v1/point/<type>', methods=['POST'])
def add_point(type):
    try:
        data = json.loads(request.data)
        title = data['title']
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        point = Point(
            title=title,
            latitude=latitude,
            longitude=longitude,
            type=type
        )
        point.put()
    except CapabilityDisabledError:
        logging.error(u'App Engine Datastore is currently in read-only mode.')
        abort(500)
    except BadValueError:
        abort(400)
    except TypeError:
        abort(400)
    except Exception as e:
        logging.error(e.args[0])
        abort(500)

    return Response(json.dumps(point.to_dict()), mimetype='application/json');


@app.route('/api/v1/point/<type>/<id>', methods=['DELETE'])
def delete_point(type, id):
    point = Point.get_by_id(int(id))
    try:
        point.key.delete()
    except CapabilityDisabledError:
        logging.error(u'App Engine Datastore is currently in read-only mode.')
        abort(500)
    except Exception as e:
        logging.error(e.args[0])
        abort(500)

    return Response(json.dumps({ 'status': 'ok' }), mimetype='application/json');


@app.route('/api/v1/tracker/config', methods=['GET'])
def get_tracker():
    tracker = Tracker.query().order(-Tracker.date_added).get()
    return Response(json.dumps(tracker.to_dict()), mimetype='application/json');


@app.route('/api/v1/tracker/config', methods=['POST'])
def save_tracker():
    try:
        data = json.loads(request.data)
        type = data['type']
        url = data['url']
        tracker = Tracker(
            type=type,
            url=url
        )
        tracker.put()
    except CapabilityDisabledError:
        logging.error(u'App Engine Datastore is currently in read-only mode.')
        abort(500)
    except BadValueError:
        abort(400)
    except TypeError:
        abort(400)
    except Exception as e:
        logging.error(e.args[0])
        abort(500)

    return Response(json.dumps(tracker.to_dict()), mimetype='application/json');


@app.route('/api/v1/tracker/load', methods=['GET'])
def load_tracker():
    tracker = Tracker.query().order(-Tracker.date_added).get()
    if tracker is None:
        return Response(json.dumps({ 'error': 'tracker configuration was not found.' }), status=500, mimetype='application/json');

    if tracker.type == 'delorme':
        return delorme.load_data(tracker.url)
    elif tracker.type == 'spot':
        return Response(json.dumps({ 'error': 'tracker not supported.' }), status=400, mimetype='application/json');
    else:
        return Response(json.dumps({ 'error': 'tracker not supported.' }), status=400, mimetype='application/json');
