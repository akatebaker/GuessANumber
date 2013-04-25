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
        currentUser = users.get_current_user()
        if not currentUser:
            self.redirect(users.create_login_url(self.request.uri))
            return

        Player().updatePlayer(currentUser.user_id(), currentUser, True)

        token = channel.create_channel(currentUser.user_id())
        allPlayers = Player().getActiveNicknames()
        currentNumber = Game().getCurrentNumber()

        template_values = {'players': allPlayers,
                           'me': currentUser.nickname(),
                           'currentNum': currentNumber,
                           'token': token,
                           'logoutUrl': users.create_logout_url(self.request.uri)}
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))


class Opened(webapp2.RequestHandler):
    def post(self):
        return


class Updater():
    game = None

    def get_game_message(self):
        gameUpdate = {
            'players': Player().getActiveNicknames(),
            'currNum': Game().getCurrentNumber()
        }
        return gameUpdate

    def get_guess_msg(self, guessVal):
        if guessVal is None:
            msg = "That's not a number!"
        elif guessVal == 0:
            msg = "You Won!"
        elif guessVal > 0:
            msg = "Too Low!"
        elif guessVal < 0:
            msg = "Too High!"
        else:
            msg = "Eek!"

        return msg

    def sendGuessUpdate(self, client_id, guessVal):
        msg = self.get_game_message()
        msg['guessMsg'] = self.get_guess_msg(guessVal)

        channel.send_message(client_id, json.dumps(msg))

    def sendUpdates(self):
        message = json.dumps(self.get_game_message())

        allPlayers = Player().getActiveIds()
        for client_id in allPlayers:
            channel.send_message(client_id, message)


class AddToChannel(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')

        Player().updatePlayer(client_id.encode('ascii'), None, True)


class RemoveFromChannel(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')

        Player().updatePlayer(client_id.encode('ascii'), None, False)


class Guess(webapp2.RequestHandler):
    def post(self):
        client_id = users.get_current_user().user_id()
        guess = self.request.get('guess').encode('ascii')
        currentNumber = int(Game().getCurrentNumber())

        try:
            guess = int(float(guess))
            Updater().sendGuessUpdate(client_id, currentNumber - guess)
        except ValueError:
            Updater().sendGuessUpdate(client_id, None)


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
        q = Player.all()
        q.filter("user_id = ", client_id)
        player = q.get()

        return player

    def getActivePlayers(self):
        allPlayers = []
        q = Player.all()
        q.filter("active = ", True)

        for p in q.run():
            allPlayers.append(p)

        return allPlayers

    def getActiveNicknames(self):
        nicknames = []
        allPlayers = self.getActivePlayers()

        for p in allPlayers:
            nicknames.append(p.nickname.encode('ascii'))

        return nicknames

    def getActiveIds(self):
        ids = []
        allPlayers = self.getActivePlayers()

        for p in allPlayers:
            ids.append(p.user_id.encode('ascii'))

        return ids

    def updatePlayer(self, client_id, currentUser, add):
        newPlayer = self.getPlayerById(client_id)
        currentGameId = Game().getCurrentGame().gameId

        if add:
            if newPlayer and newPlayer.mostRecentGame != currentGameId:
                newPlayer.active = True
                newPlayer.totalGames += 1
            elif not newPlayer and currentUser:
                if client_id == currentUser.user_id():
                    newPlayer = Player(
                        user_id=client_id,
                        nickname=currentUser.nickname(),
                        mostRecentGame=currentGameId,
                        active=True,
                        wins=0,
                        totalGames=1)
        elif newPlayer:
            print "removing player " + newPlayer.nickname
            newPlayer.active = False

        if newPlayer:
            newPlayer.put()

        Updater().sendUpdates()


jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

app = webapp2.WSGIApplication(
    [('/', MainPage),
     ('/_ah/channel/connected/', AddToChannel),
     ('/_ah/channel/disconnected/', RemoveFromChannel),
     ('/guess', Guess)
    ], debug=True)
