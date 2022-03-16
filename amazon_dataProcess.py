import numpy as np
import json
import pickle
from Utils.TimeLogger import log
from scipy.sparse import csr_matrix
import time
import scipy.sparse as sp
minn = 1647180684
maxx = 0

def transTime(date):
	timeArr = time.strptime(date, '%Y-%m-%dT%H:%M:%SZ')
	year = timeArr.tm_year*12+timeArr.tm_mon
	global minn
	global maxx
	minn = min(minn, year)
	maxx = max(maxx, year)
	return year# time.mktime(timeArr)

def mapping(infile):
	global minn
	global maxx
	usrId = dict()
	itmId = dict()
	usrid, itmid = [0, 0]
	interaction = list()
	with open(infile, 'r') as fs:
		for line in fs:
			arr = line.strip().split(',')
			row = arr[0]
			col = arr[1]
			timeStamp = int(arr[-1])
			minn = min(minn, timeStamp)
			maxx = max(maxx, timeStamp)
			if row not in usrId:
				usrId[row] = usrid
				interaction.append(dict())
				usrid += 1
			if col not in itmId:
				itmId[col] = itmid
				itmid += 1
			usr = usrId[row]
			itm = itmId[col]
			if(itm not in interaction[usr]):
				interaction[usr][itm]=[]
			interaction[usr][itm].extend([timeStamp])
	print(minn, maxx)
	return interaction, usrid, itmid

# def checkFunc1(cnt):
# 	return cnt >= 10
# def checkFunc2(cnt):
# 	return cnt >= 5
# def checkFunc3(cnt):
# 	return cnt >= 5

def checkFunc1(cnt):
	return cnt >= 20
def checkFunc2(cnt):
	return cnt >= 15
def checkFunc3(cnt):
	return cnt >= 10

def filter(interaction, usrnum, itmnum, ucheckFunc, icheckFunc, filterItem=True):
	# get keep set
	usrKeep = set()
	itmKeep = set()
	itmCnt = [0] * itmnum
	for usr in range(usrnum):
		data = interaction[usr]
		usrCnt = 0
		for col in data:
			itmCnt[col] += 1
			usrCnt += 1
		if ucheckFunc(usrCnt):
			usrKeep.add(usr)
	for itm in range(itmnum):
		if not filterItem or icheckFunc(itmCnt[itm]):
			itmKeep.add(itm)

	# filter data
	retint = list()
	usrid = 0
	itmid = 0
	itmId = dict()
	for row in range(usrnum):
		if row not in usrKeep:
			continue
		usr = usrid
		usrid += 1
		retint.append(dict())
		data = interaction[row]
		for col in data:
			if col not in itmKeep:
				continue
			if col not in itmId:
				itmId[col] = itmid
				itmid += 1
			itm = itmId[col]
			retint[usr][itm] = data[col]
	return retint, usrid, itmid

def split(interaction, usrnum, itmnum):
	pickNum = 10000
	# random pick
	usrPerm = np.random.permutation(usrnum)
	pickUsr = usrPerm[:pickNum]

	tstInt = [None] * usrnum
	exception = 0
	for usr in pickUsr:
		temp = list()
		data = interaction[usr]
		for itm in data:
			temp.append((itm, data[itm]))
		if len(temp) == 0:
			exception += 1
			continue
		temp.sort(key=lambda x: x[1])
		tstInt[usr] = temp[-1][0]
		interaction[usr][tstInt[usr]] = None
	print('Exception:', exception, np.sum(np.array(tstInt)!=None))
	return interaction, tstInt

def trans(interaction, usrnum, itmnum):
	r, c, d = [list(), list(), list()]
	for usr in range(usrnum):
		if interaction[usr] == None:
			continue
		data = interaction[usr]
		for col in data:
			if data[col] != None:
				for one_data in data[col]:
					r.append(usr)
					c.append(col)
					d.append(1.0)
	intMat = csr_matrix((d, (r, c)), shape=(usrnum, itmnum))
	return intMat

def trans_sub(interaction, usrnum, itmnum, gragh_num):
	global minn
	global maxx
	interval = (maxx-minn)/gragh_num
	rcd = [[list(), list(), list()]]
	for i in range(gragh_num-1):
		rcd.append([list(), list(), list()])
	timeMat = sp.dok_matrix((usrnum, itmnum), dtype=np.int)
	for usr in range(usrnum):
		if interaction[usr] == None:
			continue
		data = interaction[usr]
		for col in data:
			if data[col] != None:
				for one_data in data[col]:
					gragh_no=int(((one_data-minn)/interval)-1)
					# print(gragh_no,one_data)
					rcd[gragh_no][0].append(usr)
					rcd[gragh_no][1].append(usrnum+col)
					rcd[gragh_no][2].append(1.0)
					rcd[gragh_no][0].append(usrnum+col)
					rcd[gragh_no][1].append(usr)
					rcd[gragh_no][2].append(1.0)
					timeMat[usr,col]=gragh_no
	intMat=list()
	for i in range(gragh_num):
		intMat.append(csr_matrix((rcd[i][2], (rcd[i][0], rcd[i][1])), shape=(usrnum+itmnum, usrnum+itmnum)))
		# intMat.append(normalized_adj_single(csr_matrix((rcd[i][2], (rcd[i][0], rcd[i][1])), shape=(usrnum+itmnum, usrnum+itmnum))))
		print(intMat[i])
	return intMat, timeMat.tocsr()

prefix = 'D:/edgedownload/'
log('Start')
interaction, usrnum, itmnum = mapping(prefix + 'amazon_ratings_Books.csv')
log('Id Mapped, usr %d, itm %d' % (usrnum, itmnum))

checkFuncs = [checkFunc1, checkFunc2, checkFunc3]
for i in range(3):
	filterItem = True if i < 2 else False
	interaction, usrnum, itmnum = filter(interaction, usrnum, itmnum, checkFuncs[i], checkFuncs[i], filterItem)
	print('Filter', i, 'times:', usrnum, itmnum)
log('Sparse Samples Filtered, usr %d, itm %d' % (usrnum, itmnum))

trnInt, tstInt = split(interaction, usrnum, itmnum)
log('Datasets Splited')
trnMat = [trans(trnInt, usrnum, itmnum)]
subMat,timeMat=trans_sub(trnInt, usrnum, itmnum, 8)
print(timeMat)
trnMat.append(subMat)
trnMat.append(timeMat)
log('Train Mat Done')
with open(prefix+'amazon_trn_mat', 'wb') as fs:
	pickle.dump(trnMat, fs)
with open(prefix+'amazon_tst_int', 'wb') as fs:
	pickle.dump(tstInt, fs)
log('Interaction Data Saved')