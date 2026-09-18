from collective.bpmproxy import _
from plone.autoform.interfaces import IFormFieldProvider
from plone.supermodel import model
from zope import schema
from zope.interface import provider


@provider(IFormFieldProvider)
class IRenovationProjectBehavior(model.Schema):
    site_address = schema.Text(
        title=_("Site address"),
        required=False,
    )

    budget = schema.Decimal(
        title=_("Budget"),
        required=False,
    )
