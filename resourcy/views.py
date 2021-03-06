# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.forms import formset_factory
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from resourcy.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from resourcy.models import Category, Page
from registration.backends.simple.views import RegistrationView

import praw
import itertools
import os


def home(request):
    return HttpResponse("Rango says welcome partner!!")


class MyRegistrationView(RegistrationView):
    def get_success_url(self, user):
        return '/'


# A helper method
def get_server_side_cookie(request, cookie, default_val=None):
    val = request.session.get(cookie)
    if not val:
        val = default_val
    return val


def visitor_cookie_handler(request):
    # Get the number of visits to the site.
    # We use the COOKIES.get() function to obtain the visits cookie.
    # If the cookie exists, the value returned is cast into an integer.
    # If the cookie doesn't exist, then the default value of 1 is used.
    # NOTE: Anything with ## refers only to client side cookies
    ##visits = int(request.COOKIES.get('visits', '1'))
    visits = int(get_server_side_cookie(request, 'visits', '1'))

    ##last_visit_cookie = request.COOKIES.get('last_visit', str(datetime.now()))
    last_visit_cookie = get_server_side_cookie(request,
                                                'last_visit',
                                                str(datetime.now()))
    ##last_visit_time = datetime.strptime(last_visit_cookie[:-7],
                                        ##'%Y-%m-%d %H:%M:%S')

    last_visit_time = datetime.strptime(last_visit_cookie[:-7],
                                        '%Y-%m-%d %H:%M:%S')

    # If it's been more than a day since the last visit...
    if (datetime.now() - last_visit_time).seconds > 0:
        visits += 1
        print visits
        # update the last visit cookie ow that we have updated the count
        ##response.set_cookie('last_visit', str(datetime.now()))
        request.session['last_visit'] = str(datetime.now())
    else:
        print 'also works'
#        visits = visits 
        # set the last visit cookie
        ##response.set_cookie('last_visit', last_visit_cookie)
        request.session['last_visit'] = last_visit_cookie

    # Update/set the visits cookie
    ##response.set_cookie('visits', visits)
    request.session['visits'] = visits


def index(request):
    # Query the database for a list of ALL categories currently stored.
    # Order the categories by no. of likes in descending order
    # Retreive the top 5 only - or all if less than 5
    # Place the list in our context_dict dictionary
    # that will be passed to the template engine
    category_list = Category.objects.order_by('-likes')[:5]
    page_list = Page.objects.order_by('-views')[:5]

    # This gets the cookies that store the number of visits to the site
    #visits = int(request.COOKIES.get('visits', '1'))

    visitor_cookie_handler(request)

    # Construct a dictionary to pass to the template engine as its context.
    # The key boldmessage is the same as {{ boldmessage }} in the template.
    context_dict = {'categories': category_list,
                        'pages': page_list,}

    context_dict['visits'] = request.session['visits']


    # Return a rendered response to send to the client
    # We make use of the shortcut function to make our lives easier.
    # The first parameter is the template we wish to use.
    response = render(request, 'resourcy/index.html', context_dict)


    # Call function to handle the cookies
    #visitor_cookie_handler(request, response)

    # Return response back to the user, updating any cookies that need changing.
    return response


def about(request):
    # Prints out whether the method is a GET or a POST
    print(request.method)
    # Prints out the user name, if no one is logged in it prints `AnonymousUser`
    print(request.user)

    visitor_cookie_handler(request)
    context_dict = {'visits': request.session['visits']}
    return render(request, 'resourcy/about.html', context_dict)


def show_category(request, category_name_slug):
    # Create a context dictionary which we can pass to the
    # template rendering engine.
    context_dict = {}

    try:
        # Can we find a category name slug with the given name?
        # If we can't the .get() method raises a DoesNotExist exception.
        # So the .get() method returns one model instance or raises an exception
        category = Category.objects.get(slug=category_name_slug)

        # Retrieve all of the associated pages.
        # Note that filter() will return a list of page objects or an empty list
        pages = Page.objects.filter(category=category)

        # Add our results list to the template context under name pages
        context_dict['pages'] = pages
        # We also add the category object from
        # the database to the context dictionary.
        # We'll use this in the template to verify that the category exists.
        context_dict['category'] = category

    except Category.DoesNotExist:
        # We get here if we didn't find the specified category.
        # Don't do anything -
        # the template will display the "no category" message for us.
        context_dict['category'] = None
        context_dict['category'] = None

    # Go render the response and return it to the client.
    return render(request, 'resourcy/category.html', context_dict)



def categories(request):
    """We want to display all the categories in one page for viewing"""
    context_dict = {}

    all_categories = Category.objects.all()

    context_dict['categories'] = all_categories

    return render(request, 'resourcy/category_listing.html', context_dict)



def find_categories(request):
    """For the discovery of new categories by users"""
    reddit = praw.Reddit(client_id=os.environ['REDDIT_CLIENT_ID'],
                         client_secret=os.environ['REDDIT_CLIENT_SECRET'],
                         redirect_uri='http://localhost:8000/resourcy/',
                         user_agent='web app:Reddit Resources:v0.0.1 (by /u/active_blogger)')

    context_dict = {}

    category = Category.objects.all()
    context_dict['category'] = category

    resources = {}
    titles = []
    title_urls = []

    template = loader.get_template('resourcy/base.html') # Template we're interested in

    if template: # If we are in the template of interest
        if request.method == 'POST': # and user submits a POST request
            reddit_subreddit = request.POST.get('subreddit')
             # get whatever is in the form with the name subreddit
             # assign variable reddit_subreddit
             # pass it to praw as the subreddit being searched for

            context_dict['reddit_subreddit'] = reddit_subreddit

            for submissions in reddit.subreddit(reddit_subreddit).top(limit=20):
                titles.append(submissions.title)
                title_urls.append(submissions.url)


            category = Category.objects.all()
            reddit_subreddit_caps = reddit_subreddit.capitalize()
            if reddit_subreddit_caps not in category:
                form = CategoryForm(initial={
                    'name': reddit_subreddit_caps
                })

                if form.is_valid():
                    cat = form.save(commit=True)
                else:
                    print form.errors
            
                context_dict['form'] = form

    resources = dict(itertools.izip(titles, title_urls))

    context_dict['resources'] = resources
    return render(request, 'resourcy/find_categories.html', context_dict)



@login_required
def add_category(request):
    form = CategoryForm()

    # A HTTP POST?
    if request.method == 'POST':
        form = CategoryForm(request.POST)

        # Have we been provided with a valid form?
        if form.is_valid():
            # Save the new category to the database.
            cat = form.save(commit=True)
            print (cat, cat.slug)
            # Now that the category is saved
            # We could give a confirmation message
            # But since the most recent category added is on the index page
            # Then we can direct the user back to the index page.
            if request.POST.get('reddit category'):
                return HttpResponseRedirect('/resourcy/find_category/') 
            else:
                return index(request)

        else:
            # The supplied form contained errors =
            # just print them to the terminal.
            print(form.errors)

    # Will handle the bad form, new form, or no form supplied cases.
    # Render the form with error messages (if any).
    return render(request, 'resourcy/add_category.html', {'form': form})


@login_required
def add_page(request, category_name_slug):
    try:
        category = Category.objects.get(slug=category_name_slug)
    except Category.DoesNotExist:
        category = None

    form = PageForm()
    if request.method == 'POST':
        form = PageForm(request.POST)
        if form.is_valid():
            if category:
                page = form.save(commit=False)
                page.category = category
                page.views = 0
                page.save()
                return show_category(request, category_name_slug)
        else:
            print form.errors

    context_dict = {'form': form, 'category': category}
    return render(request, 'resourcy/add_page.html', context_dict)


@login_required
def restricted(request):
    return render(request, 'resourcy/restricted.html')

