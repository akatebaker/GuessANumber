#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import jinja2
import os
import webapp2
import random
import json
from google.appengine.ext import db
from google.appengine.api import channel
from google.appengine.api import users


class MainPage(webapp2.RequestHandler):
    def get(self):
        print "MAIN PAGE GET"
        currentUser = users.get_current_user()
        if not currentUser:
            self.redirect(users.create_login_url(self.request.uri))
            return

        Player().updatePlayer(currentUser.user_id(), currentUser, True)

        token = channel.create_channel(currentUser.user_id())
        allPlayers = Player().getActivePlayers()
        currentNumber = Game().getCurrentNumber()

        template_values = {'players': allPlayers,
                           'me': currentUser.user_id(),
                           'currentNum': currentNumber,
                           'token': token}
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))


class Opened(webapp2.RequestHandler):
    def post(self):
        print "OPENED"
        return


class Updater():
    game = None

    def get_game_message(self):
        print "GET GAME MESSAGE"
        gameUpdate = {
            'players': Player().getActivePlayers(),
            'currentNumber': Game().getCurrentNumber()
        }
        return json.dumps(gameUpdate)

    def sendUpdate(self, client_id):
        print "SEND UPDATE"
        message = self.get_game_message()
        print "send message -- client_id: " + client_id + " & message: " + message
        channel.send_message(client_id, message)


class AddToChannel(webapp2.RequestHandler):
    def post(self):
        print "Add to channel POST"
        client_id = self.request.get('from')

        Player().updatePlayer(client_id, None, True)

        Updater().sendUpdate(client_id)


class RemoveFromChannel(webapp2.RequestHandler):
    def post(self):
        print "Remove from channel POST"
        client_id = self.request.get('from')

        Player().updatePlayer(client_id, None, False)

        Updater().sendUpdate(client_id)


class Game(db.Model):
    currentNumber = db.IntegerProperty()
    gameId = db.IntegerProperty()

    def getCurrentGame(self):
        q = Game.all()
        game = q.get()

        if not game:
            game = Game(currentNumber=self.getRandomNumber(),
                        gameId=1)
            game.put()

        return game

    def getCurrentNumber(self):
        game = self.getCurrentGame()

        if not game.currentNumber:
            game.currentNumber = self.getRandomNumber()
            game.put()

        return game.currentNumber

    def getRandomNumber(self):
        return random.randint(1, 100)


class Player(db.Model):
    user_id = db.StringProperty()
    nickname = db.StringProperty()
    active = db.BooleanProperty()
    mostRecentGame = db.IntegerProperty()
    wins = db.IntegerProperty()
    totalGames = db.IntegerProperty()

    def getPlayerById(self, client_id):
        print "GET PLAYER BY ID: " + client_id
        q = Player.all()
        q.filter("user_id=", client_id)
        player = q.get()

        if player:
            print "GOT PLAYER: " + player
        else:
            print "GOT PLAYER: null"
        return player

    def getActivePlayers(self):
        print "GET ACTIVE PLAYERS"

        allPlayers = []
        q = Player.all()
        q.filter("active =", True)

        for p in q.run():
            print "Player: " + p.nickname
            allPlayers.append(p.nickname)

        return allPlayers

    def updatePlayer(self, client_id, currentUser, add):
        print "client_id: " + client_id

        if currentUser:
            print "currentUser: " + currentUser.user_id()
        else:
            print "currentUser: null"

        newPlayer = self.getPlayerById(client_id)
        currentGameId = Game().getCurrentGame().gameId

        if add:
            if newPlayer and newPlayer.mostRecentGame != currentGameId:
                newPlayer.active = True
                newPlayer.totalGames += 1
            elif newPlayer is None and currentUser is not None:
                if client_id == currentUser.user_id():
                    newPlayer = Player(
                        user_id=client_id,
                        nickname=currentUser.nickname(),
                        mostRecentGame=currentGameId,
                        active=True,
                        wins=0,
                        totalGames=1)
        elif newPlayer is not None:
            newPlayer.active = False

        if newPlayer is not None:
            newPlayer.put()


jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

app = webapp2.WSGIApplication(
    [('/', MainPage),
     ('/_ah/channel/connected/', AddToChannel),
     ('/_ah/channel/disconnected/', RemoveFromChannel),
     ('/opened', Opened)
    ], debug=True)
