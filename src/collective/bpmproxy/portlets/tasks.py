# -*- coding: utf-8 -*-
from __future__ import absolute_import
from Acquisition import aq_inner
from collective.bpmproxy import _
from plone import schema
from plone.app.portlets.portlets import base
from plone.memoize.instance import memoize
from plone.portlets.interfaces import IPortletDataProvider
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.form import field
from zope.component import getMultiAdapter
from zope.interface import implementer

import json
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request


class ITasksPortlet(IPortletDataProvider):
    place_str = schema.TextLine(
        title=_(u'Name of your place with country code'),
        description=_(u'City name along with country code i.e Delhi,IN'),  # NOQA: E501
        required=True,
        default=u'delhi,in'
    )


@implementer(ITasksPortlet)
class Assignment(base.Assignment):
    schema = ITasksPortlet

    def __init__(self, place_str='delhi,in'):
        self.place_str = place_str.lower()

    @property
    def title(self):
        return _(u'Weather of the place')


class AddForm(base.AddForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _(u'Add Place weather')
    description = _(u'This portlet displays weather of the place.')

    def create(self, data):
        return Assignment(
            place_str=data.get('place_str', 'delhi,in'),
        )


class EditForm(base.EditForm):
    schema = ITasksPortlet
    form_fields = field.Fields(ITasksPortlet)
    label = _(u'Edit Place weather')
    description = _(u'This portlet displays weather of the place.')


class Renderer(base.Renderer):
    schema = ITasksPortlet
    _template = ViewPageTemplateFile('tasks.pt')

    def __init__(self, *args):
        base.Renderer.__init__(self, *args)
        context = aq_inner(self.context)
        portal_state = getMultiAdapter(
            (context, self.request),
            name=u'plone_portal_state'
        )
        self.anonymous = portal_state.anonymous()

    def render(self):
        return self._template()

    @property
    def available(self):
        """Show the portlet only if there are one or more elements and
        not an anonymous user."""
        return not self.anonymous and self._data()

    def weather_report(self):
        self.result = self._data()
        return self.result['description']

    def get_humidity(self):
        return self.result['humidity']

    def get_pressure(self):
        return self.result['pressure']

    @memoize
    def _data(self):
        baseurl = 'https://query.yahooapis.com/v1/public/yql?'
        yql_query = 'select * from weather.forecast where woeid in (select woeid from geo.places(1) where text="{0}")'.format(  # NOQA: E501
            self.data.place_str,
        )
        yql_url = baseurl + six.moves.urllib.parse.urlencode(
            {'q': yql_query},
        ) + '&format=json'
        result = six.moves.urllib.request.urlopen(yql_url).read()
        data = json.loads(result)
        result = {}
        result['description'] = data['query']['results']['channel']['description']  # NOQA: E501
        result['pressure'] = data['query']['results']['channel']['atmosphere']['pressure']  # NOQA: E501
        result['humidity'] = data['query']['results']['channel']['atmosphere']['humidity']  # NOQA: E501
        return result
