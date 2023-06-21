# encoding=utf8
from gc import isenabled
from operator import is_
import discord, os, json, math, copy, re, emoji as emoji_lib, string, inspect
from discord_slash.context import ComponentContext
from num2words import num2words
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils import manage_commands, manage_components
from discord_slash.model import ButtonStyle, SlashCommandOptionType

bot = commands.Bot(command_prefix="!")
slash = SlashCommand(bot, override_type = True, sync_commands=True)

#Configuration for adjacent tile values
tile_values = [[1,2,4],[8,None,16],[32,64,128]]

#Invisible text for discord
invisible_text = "||​" + "||||​" * 198 + "|" * 12

#A check to prevent the bot from checking emoji existance more than once
global already_checked_emojis
already_checked_emojis = False

#Get general configuration
with open(os.path.join(os.path.dirname(__file__), os.path.join("configuration", "config.json")), "r") as file:
    configuration = json.load(file)

#Get wall index
with open (os.path.join(os.path.dirname(__file__), "wall_index.json"), "r") as file:
    wall_index = json.load(file)

#Get dissection info for custom encoding 
with open (os.path.join(os.path.dirname(__file__), "dissection_index.json"), "r") as file:
    dissection_index = json.load(file)

#Get index of other emotes
with open (os.path.join(os.path.dirname(__file__), "emote_index.json"), "r") as file:
    emote_index = json.load(file)

#2D ARRAYS OPERATE BASED ON Y, X WITH AN ANCHOR FROM THE TOP LEFT
#E.G (10, 2) is ten down and two over

class WallCollision(Exception): pass
class GoalCollision(Exception): pass

class Puck:
    def __init__(self, position=[0,0], array=None, velocity=[0,0]):
        self.position = position
        self.array = array
        self.sprite = emote_index["Puck"]
        self.serialization_id = 3
        self.velocity = [int(round(num)) for num in velocity]

    def update_position(self, orig_position):
        '''Moves puck by copying itself to the position it needs to be, then deleting the old one'''
        orig_position = [int(number) for number in orig_position]

        self.array[self.position[0]][self.position[1]] = self.array[orig_position[0]][orig_position[1]]
        self.array[orig_position[0]][orig_position[1]] = WhiteSpace()
    
    def advance_physics(self):
        '''Simplest way of detecting collision with an integer based 2d array (I think)'''
        #Absolutely make sure the velocity is NOT 0, 0
        self.sprite = emote_index["Puck"]
        if self.velocity == [0, 0]:
            return

        collision = [Collision, Paddle]
        goal = [GoalTile]
        global tile_sum
        global last_position
        original_position = copy.deepcopy(self.position)
        touched_goal = False

        #Convert current velocity to top left origin format
        velocity = self.velocity

        #Get biggest and smallest numbers and their indexes.
        biggest_number, big_index = biggest(velocity)
        smallest_number, small_index = smallest(velocity)

        if abs(biggest_number) == abs(smallest_number):
            big_index = 0
            small_index = 1
            biggest_number = velocity[0]
            smallest_number = velocity[1]

        #Get step incrememnt by dividing both by biggest number
        step_increment = [math.copysign(num / biggest_number, num) for num in velocity]

        #Convert step incremement to int if whole number
        for index, num in enumerate(step_increment):
            if type(num) is not int and num.is_integer():
                step_increment[index] = int(step_increment[index])

        try:
            #Do collision check at each step. Raises WallCollision if detection
            for i in range(0, abs(biggest_number)):
                local_step_pos = [local_coordinate * i for local_coordinate in step_increment]
                world_step_pos = [original_position[0] + local_step_pos[0], original_position[1] + local_step_pos[1]]


                #Round coordinates steps if they are not half steps
                for index, (local_num, world_num) in enumerate(zip(local_step_pos, world_step_pos)):
                    if local_num % 1 != .5:
                        local_step_pos[index] = round(local_num)
                    if world_num % 1 != .5:
                        world_step_pos[index] = round(world_num)
                
                #In order to show the player where the puck has been make the current step a certain sprite
                

                if type(world_step_pos[small_index]) is int:
                    #Behavior for when both coordinates are integers
                    tile_sum = None
                    last_position = None

                    #Get local adjacent tiles to check
                    local_adjacent = [[0, 0], [0, 0], [0, 0]]
                    if biggest_number != 0:
                        local_adjacent[2][big_index] = local_adjacent[0][big_index] = copysign(1, biggest_number)
                    if smallest_number != 0:
                        local_adjacent[2][small_index] = local_adjacent[1][small_index] = copysign(1, smallest_number)

                    world_adjacent = copy.deepcopy(local_adjacent)

                    #Convert local to world position
                    for index1, pos in enumerate(world_adjacent):
                        pos = [number + world_step_pos[index] for index, number in enumerate(pos)]
                        world_adjacent[index1] = pos

                    #Loop through first two and count up tile sum, and keep track of the tile indexes
                    tile_indexes = 0
                    tile_sum = 0
                    for i in range(2):
                        pos = world_adjacent[i]

                        #OOB check
                        OOB = check_out_of_bounds(pos, self.array)
                        object = None
                        if not OOB:
                            object = self.array[pos[0]][pos[1]]
                        if type(object) in collision or OOB:
                            tile_indexes += 1
                            tile_sum += tile_values[1 + local_adjacent[i][0]][1 + local_adjacent[i][1]]
                        elif type(object) in goal:
                            last_position = world_step_pos
                            raise GoalCollision

                    #If there is no tile sum check corner adjacent, else raise wall collision
                    if tile_indexes == 0:
                        pos = world_adjacent[2]

                        #OOB check
                        OOB = check_out_of_bounds(pos, self.array)
                        object = None
                        if not OOB:
                            object = self.array[pos[0]][pos[1]]
                        if type(object) in collision or OOB:
                            tile_sum += tile_values[1 + local_adjacent[2][0]][1 + local_adjacent[2][1]]
                            last_position = world_step_pos
                            raise WallCollision
                        elif type(object) in goal:
                            last_position = world_step_pos
                            raise GoalCollision
                    elif tile_indexes == 1:
                        last_position = world_step_pos
                        raise WallCollision
                    elif tile_indexes == 2:
                        tile_sum = tile_values[1 + local_adjacent[2][0]][1 + local_adjacent[2][1]]
                        last_position = world_step_pos
                        raise WallCollision
                else:
                    #Behavior for when the step is in between 2 coordinates

                    #Round the step up and down making 2 new coordinates   
                    steps_coordinates_rounded_local = [[0, 0], [0, 0]]
                    steps_coordinates_rounded_local[0][small_index], steps_coordinates_rounded_local[1][small_index] = math.floor(local_step_pos[small_index]), math.ceil(local_step_pos[small_index])
                    steps_coordinates_rounded_local[0][big_index] = steps_coordinates_rounded_local[1][big_index] = local_step_pos[big_index]

                    #Convert the coordinates to world coordinates
                    steps_coordinates_rounded_world = copy.deepcopy(steps_coordinates_rounded_local)
                    for index2, coordinate in enumerate(steps_coordinates_rounded_world):
                        steps_coordinates_rounded_world[index2] = [num + self.position[index] for index, num in enumerate(coordinate)]

                    #Make list of which coordinates to check in order
                    #The first coordinate will be the local coordinate that's closer to the local end position (the velocity)
                    numbers_to_compare = [steps_coordinates_rounded_local[0][small_index], steps_coordinates_rounded_local[1][small_index]]
                    priority_index = numbers_to_compare.index(closest(numbers_to_compare, smallest_number))
                    priority_list = [priority_index, priority_index - 1]

                    #Get local adjacent coordinate
                    adjacent_tile_to_check_local = [0, 0]
                    adjacent_tile_to_check_local[big_index] = copysign(1, biggest_number)

                    #Loop through coordinate steps and check a specific adjacent tile to that step
                    for index in priority_list:
                        step_pos_world = steps_coordinates_rounded_world[index]
                        adjacent_tile_to_check_world = [step_pos_world[0] + adjacent_tile_to_check_local[0], step_pos_world[1] + adjacent_tile_to_check_local[1]]

                        #Check if out of bounds first then get object from array
                        object = None
                        OOB = check_out_of_bounds(adjacent_tile_to_check_world, self.array)
                        if not OOB:
                            object = self.array[adjacent_tile_to_check_world[0]][adjacent_tile_to_check_world[1]]
                        #Check if object type is collision
                        if type(object) in collision or OOB:
                            tile_sum = tile_values[1 + adjacent_tile_to_check_local[0]][1 + adjacent_tile_to_check_local[1]]
                            last_position = step_pos_world
                            raise WallCollision
                        elif type(object) in goal:
                            last_position = world_step_pos
                            raise GoalCollision

                    
        except WallCollision:
            #Update position to last position, update sprite to show collision direction
            self.position = last_position
            self.sprite = emote_index[f"PuckCollision{tile_sum}"]

            #Convert tile sum back into a local value with list comprehension (looking up the tile sum in the tile values 2d array)
            adjacent = ["{} {}".format(index1,index2) for index1,value1 in enumerate(tile_values) for index2,value2 in enumerate(value1) if value2==tile_sum]
            #Make them integers and make origin from the middle
            adjacent = [int(value) - 1 for value in list(adjacent[0].replace(" ", ""))]

            #Decrease velocity by 1 and invert the direction 
            if adjacent[0] != 0:
                sign = copysign(1, self.velocity[0]) * -1
                self.velocity[0] = copysign(abs(self.velocity[0]) - 1, sign)
            if adjacent[1] != 0:
                sign = copysign(1, self.velocity[1]) * -1
                self.velocity[1] = copysign(abs(self.velocity[1]) - 1, sign)
        except GoalCollision:
            self.position = last_position
            self.sprite = emote_index['PuckFinish']
            touched_goal = True
        else:
            #This means no collision was detected and the puck will be moved to exactly the local position it should be (the velocity)
            self.position[0] += self.velocity[0]
            self.position[1] += self.velocity[1]
            last_position = self.position
        finally:
            self.position = [int(num) for num in self.position]
            if original_position != last_position:
                self.update_position(original_position)
            if touched_goal:
                return "finish"

class Paddle:
    def __init__(self, position=[0,0], array=None):
        self.position = position
        self.array = array
        self.sprite = emote_index["PaddleMiddle"]
        self.serialization_id = 4
    def add_sides(self):
        direct_adjacent = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for tile in direct_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if adjacent_position[0] < 0 or adjacent_position[1] < 0:
                    continue

                object = self.array[adjacent_position[0]][adjacent_position[1]]

                if type(object) is WhiteSpace:
                    object.sprite = emote_index[f"Paddle{tile_values[1 + tile[0]][1 + tile[1]]}"]
            except IndexError:
                continue
    def remove_sides(self):
        direct_adjacent = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for tile in direct_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if check_out_of_bounds(adjacent_position, self.array):
                    continue

                object = self.array[adjacent_position[0]][adjacent_position[1]]

                if type(object) is WhiteSpace:
                    object.sprite = emote_index["Whitespace"]
            except IndexError:
                continue
    def move_paddle(self, pos):
        direct_adjacent = [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

        if pos == self.position:
            return "self"

        blacklisted_objects = [Collision, Puck, GoalTile]
        #Check if object paddle wants to move to is out of bounds
        if check_out_of_bounds(pos, self.array):
            return "bounds"
        moveto_object = self.array[pos[0]][pos[1]]
        if type(moveto_object) in blacklisted_objects:
            return "badtile"
        elif type(moveto_object) == None:
            return "bounds"
        self.array[pos[0]][pos[1]] = self.array[self.position[0]][self.position[1]]
        self.array[self.position[0]][self.position[1]].remove_sides()
        self.array[self.position[0]][self.position[1]] = WhiteSpace()
        add_velocity = [pos[0] - self.position[0], pos[1] - self.position[1]]
        self.position = pos
        self.add_sides()

        for adjacent_local_pos in direct_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_world_pos = [self.position[0] + adjacent_local_pos[0], self.position[1] + adjacent_local_pos[1]]
                if check_out_of_bounds(adjacent_world_pos, self.array):
                    continue

                object = self.array[adjacent_world_pos[0]][adjacent_world_pos[1]]

                if type(object) is Puck:
                    object.velocity[0] += add_velocity[0]
                    object.velocity[1] += add_velocity[1]
                    object.sprite = emote_index[f"PuckCollision{tile_values[adjacent_local_pos[0] * -1 + 1][adjacent_local_pos[1] * -1 + 1]}"]
            except IndexError:
                continue

class GoalTile:
    def __init__(self, position=[0,0], array=None):
        self.position = position
        self.array = array
        self.sprite = emote_index["GoalTile"]
        self.serialization_id = 5

class Collision:
    def __init__(self, position=[0,0], array=None, sprite_ID=None):
        self.position = position
        self.array = array
        self.serialization_id = 2
        try:
            self.sprite = wall_index[str(sprite_ID)]
            self.sprite_ID = sprite_ID
            self.definite_sprite = True
        except KeyError:
            self.sprite = wall_index["0"]
            self.sprite_ID = 0
            self.definite_sprite = False

    def update_self(self):
        '''Update own tile based on surrounding tiles'''
        #Get all 8 adjacent tiles
        direct_adjacent = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        corner_adjacent = [(1, 1, (64, 16)), (1, -1, (8, 64)), (-1, 1, (2, 16)), (-1, -1, (8, 2))] #adj tile, adj tile, required values
        detected_tiles = []

        #Get adjacent tiles around self and get the sum of their adjacent positions to determine own sprite
        sprite_ID = 0
        for tile in direct_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if adjacent_position[0] < 0 or adjacent_position[1] < 0:
                    continue

                object = self.array[adjacent_position[0]][adjacent_position[1]]

                #Check if the object is of type Collision
                if type(object) is Collision:
                    sprite_ID += tile_values[1 + tile[0]][1 + tile[1]]
                    #This is for handling corners
                    detected_tiles.append(tile_values[1 + tile[0]][1 + tile[1]])
            except IndexError:
                continue
        #Take into account corner adjacents if there are 2 normally adjacent to it 
        for tile in corner_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if adjacent_position[0] < 0 or adjacent_position[1] < 0:
                    continue

                #Determine if tile should be taken into account
                no_tile = False
                for requirement in tile[2]:
                    if requirement not in detected_tiles:
                        no_tile = True
                        break
                if no_tile:
                    continue

                object = self.array[adjacent_position[0]][adjacent_position[1]]

                #Check if the object is of type Collision
                if type(object) is Collision:
                    sprite_ID += tile_values[1 + tile[0]][1 + tile[1]]

            except IndexError:
                continue
        try:
            self.sprite = wall_index[str(sprite_ID)]
            self.sprite_ID = sprite_ID
        except KeyError:
            self.sprite = wall_index["0"]
            self.sprite_ID = 0

    def update_surrounding(self):
        '''Update all tiles around as well as self'''
        #8 adjacent tiles
        direct_adjacent = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        corner_adjacent = [(1, 1, (64, 16)), (1, -1, (8, 64)), (-1, 1, (2, 16)), (-1, -1, (8, 2))] #adj tile, adj tile, required values
        detected_tiles = []

        #Update all adjacent tiles as well as update own self
        sprite_ID = 0
        for tile in direct_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if adjacent_position[0] < 0 or adjacent_position[1] < 0:
                    continue

                object = self.array[adjacent_position[0]][adjacent_position[1]]

                #Check if the object is of type Collision
                if type(object) is Collision:
                    object.update_self()
                    sprite_ID += tile_values[1 + tile[0]][1 + tile[1]]
                    #This is for handling corners
                    detected_tiles.append(tile_values[1 + tile[0]][1 + tile[1]])
            except IndexError:
                continue
                #Take into account corner adjacents if there are 2 normally adjacent to it 
        for tile in corner_adjacent:
            try:
                #Make sure the adjacent tile isn't a negative value
                adjacent_position = [self.position[0] + tile[0], self.position[1] + tile[1]]
                if adjacent_position[0] < 0 or adjacent_position[1] < 0:
                    continue

                #Determine if tile should be taken into account
                no_tile = False
                for requirement in tile[2]:
                    if requirement not in detected_tiles:
                        no_tile = True
                        break

                #Check if the object is of type Collision & update it
                if type(object) is Collision:
                    object.update_self()
                    if not no_tile:
                        sprite_ID += tile_values[1 + tile[0]][1 + tile[1]]

            except IndexError:
                continue

        try:
            self.sprite = wall_index[str(sprite_ID)]
            self.sprite_ID = sprite_ID
        except KeyError:
            self.sprite = wall_index["0"]
            self.sprite_ID = 0  

class WhiteSpace:
    def __init__(self):
        self.sprite = emote_index['Whitespace']
        self.serialization_id = 1

def smallest(list):
    abslist = [abs(num) for num in list]
    index = abslist.index(min(abslist))
    return list[index], index

def biggest(list):
    '''Determine the biggest abosolute number in a list then return its value and index'''
    abslist = [abs(num) for num in list]
    index = abslist.index(max(abslist))
    return list[index], index

def closest(lst, K):
    '''Caclulate what number in list is closest to x number'''
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i]-K))]

def round(x):
    '''School rounding to nearest integer rather than nearest even number'''
    i, f = divmod(x, 1)
    return int(i + ((f >= 0.5) if (x > 0) else (f > 0.5)))

def convert_origin_bottom_left(list):
    '''Convert -y x notation to x y'''
    return [list[1], list[0] * -1]

def copysign(x, y):
    '''Return an int instead of float with regular math.copysign'''
    return int(math.copysign(x, y))

def check_out_of_bounds(position, array):
    try:
        position = [int(num) for num in position]
        if position[0] < 0 or position[1] < 0:
            return True
        thing = array[position[0]][position[1]]
    except IndexError:
        return True
    else:
        return False

def visualize_level(level):
    visual = ""
    rownum = 0
    for row in level:
        visual += emoji_lib.emojize(f':regional_indicator_{string.ascii_lowercase[rownum]}:', use_aliases=True)
        rownum += 1
        for item in row:
            try:
                visual += str(item.sprite)
            except AttributeError:
                visual += emote_index['Transparent']
        visual += "\n"
    return visual

def update_all_collision(level):
    for row in level:
        for item in row:
            if isinstance(item, Collision):
                if not item.definite_sprite:
                    item.update_self()
    return level

def serialize_level(level, should_encode=True):
    '''Serialize level with or without encoding'''
    serialized_level = ""
    if should_encode:
        already_added_velocity = False
        #Then the level
        for row in level:
            serialized_level += '\u200C' #New row marker
            for item in row:
                serialized_level += '\u206F' #New object marker
                try:
                    if type(item) is Collision:
                        serialized_level += '\u200B' + ''.join([dissection_index[num] for num in str(item.sprite_ID)])
                    else:
                        if type(item) is Puck and not already_added_velocity:
                            #Add velocity to beginning 
                            serialized_level = ''.join([dissection_index[num] for num in str(item.velocity[1])]) + '\u200F' + serialized_level #X velocity
                            serialized_level = ''.join([dissection_index[num] for num in str(item.velocity[0])]) + '\u200E' + serialized_level #Y velocity
                            already_added_velocity = True
                        serialized_level += ''.join([dissection_index[num] for num in str(item.serialization_id)])
                except AttributeError:
                    serialized_level += '\u2060'
    else:
        serialized_level = {"vel": [], "lvl": []}
        #Debug normal data dump for use with json
        for row in level:
            serialized_row = []
            for item in row:
                try:
                    if type(item) is Collision:
                        serialized_row.append(str(item.sprite_ID))
                    else:
                        if type(item) is Puck:
                            serialized_level['vel'] = item.velocity
                        serialized_row.append(item.serialization_id)
                except AttributeError:
                    serialized_row.append(0)
            serialized_level["lvl"].append(serialized_row)
            
    return serialized_level

def deserialize_level(level, is_encoded=True):
    '''
    Deserialize level by converting numbers to objects, works with json loads and already encoded string
    0 - nothing
    1 - whitespace
    2 - collision
    3 - puck
    4 - paddle
    5 - goal
    string format "0-255" - collision with sprite number
    '''
    paddle = None
    puck = None
    deserialized_level = []
    level_dimensions = [0, 0] #Amount of rows, amount of coloumns

    velocity = [0, 0]
    if is_encoded:
        #Exctract velocity and remove it
        velocity[0], level = int(''.join([dissection_index[character] for character in level.split("\u200E")[0]])), level.split("\u200E")[1]
        velocity[1], level = int(''.join([dissection_index[character] for character in level.split("\u200F")[0]])), level.split("\u200F")[1]

        #Use regex expression to seperate the unencoded rows by the character U+200C
        level = re.findall("([^{}]+)".format('\u200C'), level)
    else:
        velocity = level['vel']
        level = level['lvl']

    #Set amount of rows
    level_dimensions[0] = len(level)

    for row_index, row in enumerate(level):
        deserialized_row = []

        #Use regex expression to seperate row objects by the character U+206F
        if is_encoded:
            row = re.findall("([^{}]+)".format('\u206F'), row)

        #Set amount of columns if row has more has more objects
        if len(row) > level_dimensions[1]:
            level_dimensions[1] = len(row)

        for item_index, object_id in enumerate(row):
            #Decode object if is encoded

            if is_encoded:
                if object_id[0] == '\u200B':
                    #Properly decodes but leaves as string because it is collision with a specific sprite ID

                    object_id = object_id[1:] #Trim first character as it is just a marker for being a collision object with ID
                    object_id = ''.join([dissection_index[character] for character in object_id])
                else:
                    object_id = int(''.join([dissection_index[character] for character in object_id]))

            if type(object_id) is int:
                if object_id == 0:
                    deserialized_row.append(None)
                elif object_id == 1:
                    deserialized_row.append(WhiteSpace())
                elif object_id == 2:
                    deserialized_row.append(Collision([row_index, item_index], deserialized_level))
                elif object_id == 3:
                    deserialized_row.append(Puck(velocity=velocity, position=[row_index, item_index], array=deserialized_level))
                    puck = deserialized_row[-1]
                elif object_id == 4:
                    deserialized_row.append(Paddle([row_index, item_index], deserialized_level))
                    paddle = deserialized_row[-1]
                elif object_id == 5:
                    deserialized_row.append(GoalTile([row_index, item_index], deserialized_level))
                else:
                    deserialized_row.append(None)
            elif type(object_id) is str:
                #Objects that are strings are collision with a specific ID
                deserialized_row.append(Collision([row_index, item_index], deserialized_level, int(object_id)))

        deserialized_level.append(deserialized_row)

    #Add sides to the paddle
    try:
        paddle.add_sides()
    except: pass

    #Auto tile level collision
    deserialized_level = update_all_collision(deserialized_level)
    return {"level": deserialized_level, "puck_object": puck, "paddle_object": paddle, "level_dimensions": level_dimensions}
    
def generate_column_emojis(row_length):
    message = "⬛"
    for number in range(1, row_length+1):
        if number < 11:
            message += emoji_lib.emojize(f":{num2words(number)}:", use_aliases=True)
        else:
            message += emote_index["num" + str(number)]
    return message
        

def generate_action_rows(level_dimensions, ctx):
    #Make selections for places paddle can move to
    selection_fields = []
    for num in range(1, max(level_dimensions) + 1):
        #Generate emojis for row
        if num < 11:
            column_emoji = emoji_lib.emojize(f":{num2words(num)}:", use_aliases=True)
        else:
            column_emoji = emote_index["num" + str(num)]
            column_emoji = discord.PartialEmoji(name=column_emoji.split(":")[1], id=column_emoji.split(":")[2][:-1], animated=False)
        selection_fields.append(manage_components.create_select_option(f"Row {string.ascii_lowercase[num-1]}", value=f"row{num-1}", emoji=emoji_lib.emojize(f':regional_indicator_{string.ascii_lowercase[num-1]}:', use_aliases=True)))
        selection_fields.append(manage_components.create_select_option(f"Column {num}", value=f"col{num-1}", emoji=column_emoji))

    #Trim if over 25
    #while len(selection_fields) > 25:
    selection_fields.remove(selection_fields[-1])

    paddle_movement_options = manage_components.create_select(
        options=selection_fields,
        placeholder="Move Paddle...",
        min_values=2,
        max_values=2,
        custom_id=f"{ctx.author.id}move_paddle"
    )
    buttons = [
            manage_components.create_button(
                style=ButtonStyle.green,
                label="Advance Physics",
                custom_id=f"{ctx.author.id}advance_physics"
            ),
          ]
    return manage_components.create_actionrow(*buttons), manage_components.create_actionrow(paddle_movement_options)



@bot.event
async def on_ready():
    global already_checked_emojis
    print(f"I am running on {bot.user.name}")
    print(f"With the ID: {bot.user.id}")

    '''channel = bot.get_channel(885681921462513698)
    embed = discord.Embed(title=":white_large_square::blue_square:﻿:blue_square:﻿:blue_square:﻿:blue_square:﻿:blue_square:﻿:blue_square:﻿:blue_square:", description=":blue_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿\n:blue_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿\n:blue_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿\n:blue_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿\n:blue_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:﻿:red_square:")
    embed.add_field(name='Info', value="Velocity: (0,0)\n Foo: Bar", inline=True)
    embed.set_author(name="Level X:", icon_url=bot.user.avatar_url)
    await channel.send(embed=embed)'''

    #Check to see if the server ID you provided was right. Else terminate
    emote_guild_1 = bot.get_guild(configuration['emote_server_id'])
    emote_guild_2 = bot.get_guild(configuration['emote_server_id_2'])
    if emote_guild_1 == None:
        print("\u274C Error. The guild ID you have put in for 'emote_server_id' is invalid.")
        os._exit(1)
    if emote_guild_2 == None:
        print("\u274C Error. The guild ID you have put in for 'emote_server_id_2' is invalid.")
        os._exit(1)

    if not already_checked_emojis:
        print(f"Gathering emotes from guilds '{emote_guild_1}' and '{emote_guild_2}' now...")
        #Then check if the server you provided has the required emotes
        for key, value in {**wall_index, **emote_index}.items():
            #Get emoji, if none then warn user and terminate
            
            emoji = discord.utils.get(emote_guild_1.emojis, name=value)

            if emoji == None:
                emoji = discord.utils.get(emote_guild_2.emojis, name=value)
                if emoji == None:
                    print(f"\u274C Error. Your server is missing emote '{value}'")
                    os._exit(1)

            emoji = str(emoji)

            #Get rid of any beginning letters discord decided to haphazardly add....
            while True:
                if emoji[1] != ":":
                    emoji = emoji[:1] + emoji[2:]
                else:
                    break

            #Based on whether the key can be converted back to a number determines the origin of the emote dict
            try:
                int(key)
                wall_index[key] = emoji
            except ValueError:
                emote_index[key] = emoji

    print('PuckIt Discord Game Bot is ready to be used!')
    
@bot.event
async def on_component(ctx: ComponentContext):
    #Split id into user id and name
    id = re.match("([0-9]*)", ctx.custom_id).groups()[0]

    #If the command even has a required user (will return '' if no id within custom_id)
    if id != '':
        #If user is not expected user then let them know
        if str(ctx.author.id) != id:
            embed = discord.Embed(title="\u274C Error.", description="You did not start this game.", color=discord.Colour.red())
            await ctx.send(embed=embed, hidden=True)
            return 
        command = ctx.custom_id[len(id):]
    else:
        command = ctx.custom_id
    
    #Execute the command
    await eval(command)(ctx)

async def move_paddle(ctx: ComponentContext):
    #Turn coordinates into dictionary via slicing
    coord_dict = {ctx.selected_options[0][:3]: ctx.selected_options[0][3:], ctx.selected_options[1][:3]: ctx.selected_options[1][3:]}
    #Check if dictionary is missing 'row' or 'col'
    if 'row' not in coord_dict or 'col' not in coord_dict:
        embed = discord.Embed(title="\u274C Error.", description="You cannot pick two rows or columns!", color=discord.Colour.red())
        await ctx.send(embed=embed, hidden=True)
        return

    #Get the original message via fetch since components don't automatically return it
    channel = bot.get_channel(ctx.channel_id)
    message = await channel.fetch_message(ctx.origin_message_id)
    #Serialize the level
    level_components = deserialize_level(message.content)
    level = level_components['level']
    level_dimensions = level_components['level_dimensions']

    puck = level_components['puck_object']

    #Move paddle
    paddle = level_components['paddle_object']
    status = paddle.move_paddle([int(coord_dict["row"]), int(coord_dict["col"])])
    if status == "badtile":
        embed = discord.Embed(title="\u274C Error.", description="The tile you are trying to move the paddle to is not whitespace.", color=discord.Colour.red())
        await ctx.send(embed=embed, hidden=True)
        return
    elif status == "bounds":
        embed = discord.Embed(title="\u274C Error.", description="You cannot move the paddle out of bounds.", color=discord.Colour.red())
        await ctx.send(embed=embed, hidden=True)
        return
    elif status == "self":
        embed = discord.Embed(title="\u274C Error.", description="You cannot move the paddle to itself!", color=discord.Colour.red())
        await ctx.send(embed=embed, hidden=True)
        return

    #Level processing
    level = update_all_collision(level)
    level_visual = visualize_level(level)
    serialized_level = serialize_level(level)

    #Embed
    embed = discord.Embed(description=level_visual, title=generate_column_emojis(level_dimensions[1]))
    embed.add_field(name="velocity", value=str(convert_origin_bottom_left(puck.velocity)))

    #Send
    await ctx.edit_origin(content=serialized_level,embed=embed)

async def advance_physics(ctx: ComponentContext):
    #Get the original message via fetch since components don't automatically return it
    channel = bot.get_channel(ctx.channel_id)
    message = await channel.fetch_message(ctx.origin_message_id)

    #Serialize the level
    level_components = deserialize_level(message.content)
    level = level_components['level']
    level_dimensions = level_components['level_dimensions']


    #Advance the puck's physics
    puck = level_components['puck_object']
    result = puck.advance_physics()
    paddle = level_components['paddle_object']
    paddle.add_sides()

    #Level processing
    level = update_all_collision(level)
    level_visual = visualize_level(level)
    serialized_level = serialize_level(level)

    #Embed, Send
    embed = discord.Embed(description=level_visual, title=generate_column_emojis(level_dimensions[1]))
    if result == "finish":
        embed.add_field(name="You win!", value="You win! Now go play another level.")
        await ctx.edit_origin(content=serialized_level,embed=embed, components=None)
    else:
        embed.add_field(name="velocity", value=str(convert_origin_bottom_left(puck.velocity)))
        await ctx.edit_origin(content=serialized_level,embed=embed)

@slash.slash(name="custom", description="Start a custom level you made!", options=[manage_commands.create_option(
    name="level",
    description="Your custom level.",
    option_type= SlashCommandOptionType.STRING,
    required=True
)])
async def custom(ctx: SlashContext, level):
    try:
        input = json.loads(level)
        level_components = deserialize_level(input, is_encoded=False)
    except:
        embed = discord.Embed(title="\u274C Error.", description="Your level could not be loaded. Please double check you have properly copied and pasted it.", color=discord.Colour.red())
        await ctx.reply(embed=embed, hidden=True)
        return

    level_dimensions = level_components['level_dimensions']
    puck = level_components['puck_object']
    level = level_components['level']

    puck = level_components['puck_object']
    paddle = level_components['paddle_object']
    if puck == None or paddle == None:
        embed = discord.Embed(title="\u274C Error.", description="Your level does not contain a paddle / puck!", color=discord.Colour.red())
        await ctx.reply(embed=embed, hidden=True)
        return

    #Level processing
    level_visual = visualize_level(level)
    serialized_level = serialize_level(level)

    #Embed
    embed = discord.Embed(title=generate_column_emojis(level_dimensions[1]), description=level_visual)
    embed.add_field(name="Puck Velocity:", value=str(convert_origin_bottom_left(puck.velocity)), inline=False)
    embed.add_field(name="Game Info:", value=f"Game started by: {ctx.author.name}#{ctx.author.discriminator}", inline=False)

    #Send
    await ctx.reply(content=serialized_level,embed=embed, components=generate_action_rows(level_dimensions, ctx))

@slash.slash(name="start", description="Start a game of PuckIt turn based!")
async def start(ctx: SlashContext):
    level_components = deserialize_level({"vel": [0, 0],'lvl': [["80","24","24","24","88","24","24","24","88","24","24","24","72"],["66",1,1,4,"66",0,0,0,"66",5,5,5,"66"],["66",1,1,1,"66",0,0,0,"66",1,1,1,"66"],["66",3,1,1,"66",0,0,0,"66",1,1,1,"66"],["66",1,1,"80","10",0,0,0,"18","72",1,1,"66"],["66",1,1,"66",0,0,0,0,0,"66",1,1,"66"],["66",1,1,"82","24","24","24","24","24","10",1,1,"66"],["66",1,1,"2",1,1,1,1,1,1,1,1,"66"],["66",1,1,1,1,1,1,1,1,1,1,1,"66"],["66",1,1,1,1,1,1,1,1,"64",1,1,"66"],["18","24","24","24","24","24","24","24","24","26","24","24","10"]]

}, is_encoded=False)

    level_dimensions = level_components['level_dimensions']
    puck = level_components['puck_object']
    level = level_components['level']

    puck = level_components['puck_object']
    paddle = level_components['paddle_object']
    if puck == None or paddle == None:
        embed = discord.Embed(title="\u274C Error.", description="Your level does not contain a paddle / puck!", color=discord.Colour.red())
        await ctx.reply(embed=embed, hidden=True)
        return

    #Level processing
    level_visual = visualize_level(level)
    serialized_level = serialize_level(level)

    #Embed
    embed = discord.Embed(title=generate_column_emojis(level_dimensions[1]), description=level_visual)
    embed.add_field(name="Puck Velocity:", value=str(convert_origin_bottom_left(puck.velocity)), inline=False)
    embed.add_field(name="Game Info:", value=f"Game started by: {ctx.author.name}#{ctx.author.discriminator}", inline=False)

    #Send
    await ctx.reply(content=serialized_level,embed=embed, components=generate_action_rows(level_dimensions, ctx))

def main():
    bot.run(configuration['token'])
    #https://discord.com/api/oauth2/authorize?client_id=855274838239477780&permissions=139586816064&scope=bot

if __name__ == "__main__":
    main()
