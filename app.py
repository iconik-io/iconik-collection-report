import requests
import argparse
import datetime
import csv
import json
import getpass

#provide an interface to run from the cli without a config file
parser = argparse.ArgumentParser(description='Creates a collection report output file from contents of a collection')
parser.add_argument('-a','--app-id',dest='app_id',type=str,help="iconik AppID")
parser.add_argument('-t','--token',dest='token',type=str, help="iconik App Token")
parser.add_argument('-i','--iconik-host',dest='host',type=str,help="URL for iconik domain, default is 'https://app.iconik.io'",default='https://app.iconik.io/')
parser.add_argument('-c','--collection-id',dest='collection_id',type=str,help="Collection ID to run report on")
parser.add_argument('-o','--output-dir',dest='output_dir',type=str,help="Local path to store report")
cli_args = parser.parse_args()

if cli_args.app_id is None or cli_args.token is None:
	auth_method = "simple"
else:
	auth_method = "api"

#format our iconik headers for quick use - this means using the simple auth endpoint to get our appID/token if none are specified
#if no one has set app id or token in CLI or config, let's ask for a username and password
if auth_method == "simple":
	print("No App ID or Token specified in CLI or config file, assuming standard auth")
	username = input("iconik username: ")
	password = getpass.getpass("iconik password: ")
	r = requests.post('https://app.iconik.io/API/auth/v1/auth/simple/login/',headers={'accept':'application/json','content-type':'application/json'},data=json.dumps({'app_name':'WEB','email':username,'password':password}))
	if r.status_code == 201:
		app_id = r.json()['app_id']
		token = r.json()['token']
	else:
		print('Auth failed - status code ' + str(r.status_code))
		for error in r.json()['errors']:
			print(error)
		exit()
#if app_id and token are set, use them and bypass simple auth		
else:
	app_id = cli_args.app_id
	token = cli_args.token

recursive_search_query = {
	"query": "ancestor_collections:" + cli_args.collection_id,
	"doc_types": [
		"assets",
		"collections"
	],
	"filter": {
		"operator": "AND",
		"terms": [
			{
				"name": "status",
				"value": "ACTIVE"
			}
		]
	},
	"facets_filters": [],
	"search_fields": [
		"title",
		"description",
		"segment_text",
		"file_names.lower",
		"metadata",
		"transcription_text"
	],
	"facets": [],
	"sort": [
		{
			"name": "date_created",
			"order": "desc"
		}
	]
}

headers = {'App-ID':app_id,'Auth-Token':token,'accept':'application/json','content-type':'application/json'}

def convert_ms_to_human(millis):
	seconds=(millis/1000)%60
	minutes=(millis/(1000*60))%60
	hours=(millis/(1000*60*60))%24
	hours=(millis/(1000*60*60))%24
	days=(millis/(1000*60*60*24))%365
	return f"{days:.2f} Days Total, {hours:.2f} Hours, {minutes:.2f} Minutes, {seconds:.2f} Seconds of total content"


def get_collection_contents(collection_id):
	r = requests.post(cli_args.host + 'API/search/v1/search/',data=json.dumps(recursive_search_query),headers=headers,params={'per_page':'150','scroll':'true','generate_signed_url':'false','save_search_history':'false'})
	if r.status_code == 200:
		results = r.json()['objects']
		while len(r.json()['objects']) > 0:
			r = requests.post(cli_args.host + 'API/search/v1/search',headers=headers,params={'scroll':'true','scroll_id':r.json()['scroll_id']},data=json.dumps(recursive_search_query))
			results = results + r.json()['objects']
		return results
	else:
		return False

collection_items = get_collection_contents(cli_args.collection_id)

total_length = 0
format_count = {}
storage_aggregate = {}
asset_count = 0
collection_count = 0
video_count = 0
audio_count = 0
image_count = 0
other_count = 0

if collection_items:
	for this_item in collection_items:
		if 'media_type' in this_item:
			if this_item['media_type'] == 'video':
				video_count +=1
			elif this_item['media_type'] == 'audio':
				audio_count +=1
			elif this_item['media_type'] == 'image':	
				image_count +=1
			else:
				other_count +=1
		if this_item['object_type'] == 'assets':
			asset_count +=1
		elif this_item['object_type'] == 'collections':
			collection_count += 1
		try:
			total_length = total_length + float(this_item['duration_milliseconds'])
		except:
			pass
		if 'files' in this_item:
			for this_file in this_item['files']:
				if this_file['storage_id'] in storage_aggregate:
					storage_aggregate[this_file['storage_id']] = float(this_file['size']) + storage_aggregate[this_file['storage_id']]
				else:
					storage_aggregate[this_file['storage_id']] = float(this_file['size'])
		if 'formats' in this_item:
			for this_format in this_item['formats']:
				if this_format['name'] in format_count:
					format_count[this_format['name']] = format_count[this_format['name']] + 1
				else:
					format_count[this_format['name']] = 1

'''
print(total_length)
print(format_count)
print(asset_count)
print(collection_count)
print(storage_aggregate)
print(video_count)
print(audio_count)
print(image_count)
print(other_count)
'''
print(f"Storage report for collection ID {cli_args.collection_id}")
print(convert_ms_to_human(total_length))
print(f"Total Assets: {asset_count}")
print(f"Total Collections: {collection_count}")
print(f"Total Video assets: {video_count}")
print(f"Total Audio assets: {audio_count}")
print(f"Total Image assets: {image_count}")
print(f"Total Other assets: {other_count}")

total_storage = 0
storage_names = {}
for key in storage_aggregate:
	total_storage = total_storage + storage_aggregate[key]
	r = requests.get(cli_args.host + '/API/files/v1/storages/' + key,headers=headers)
	if r.status_code == 200:
		storage_names[key] = r.json()['name']
	gb = float(storage_aggregate[key]/1024/1024/1024)
	if gb < 1024:
		print(f"Total storage used on {storage_names[key]} is {gb:.2f} GB")
	else:
		tb = gb/1024
		print(f"Total storage used on {storage_names[key]} is {tb:.2f} TB")

gb = float(total_storage/1024/1024/1024)
if gb < 1024:
	print(f"Total storage used on all storages is {gb:.2f} GB")
else:
	tb = gb/1024
	print(f"Total storage used on all storages is {tb:.2f} TB")

for key in format_count:
	print(f"Total {key} formats: {format_count[key]}")

