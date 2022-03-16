from mimetypes import init
from sre_parse import expand_template
import numpy as np
import json
import pickle
# from Utils.TimeLogger import log
from scipy.sparse import csr_matrix
import time
import scipy.sparse as sp
def ok(year):
	return True
	if year >= 2016 and year <= 2019:
		return True
minn = 2022*12
maxx = 0
def transTime(date):
	timeArr = time.strptime(date, '%Y-%m-%dT%H:%M:%SZ')
	year = timeArr.tm_year*12+timeArr.tm_mon
	global minn
	global maxx
	minn = min(minn, year)
	maxx = max(maxx, year)
	if ok(year):
		return year# time.mktime(timeArr)
	return None

def mapping(infile):
	usrId = dict()
	itmId = dict()
	usrid, itmid = [0, 0]
	interaction = list()
	with open(infile, 'r', encoding='utf-8') as fs:
		for line in fs:
			arr = line.strip().split()
			# print(arr)
			row = int(arr[0])
			col = int(arr[-1])
			timeStamp = transTime(arr[1])
			if timeStamp is None:
				continue
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
			# print(interaction)
	print(minn, maxx)
	return interaction, usrid, itmid

def checkFunc1(cnt):
	return cnt >= 10
def checkFunc2(cnt):
	return cnt >= 5
def checkFunc3(cnt):
	return cnt >= 5

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
'''
def trans_sub(interaction, usrnum, itmnum, gragh_num):
	global minn
	global maxx
	interval = (maxx-minn)/gragh_num
	rcd = [[list(), list(), list()]]
	for i in range(gragh_num-1):
		rcd.append([list(), list(), list()])
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
					rcd[gragh_no][1].append(col)
					rcd[gragh_no][2].append(1.0)
	intMat=list()
	for i in range(gragh_num):
		intMat.append(tran_to_sym(csr_matrix((rcd[i][2], (rcd[i][0], rcd[i][1])), shape=(usrnum, itmnum))))
		# intMat.append(csr_matrix((rcd[i][2], (rcd[i][0], rcd[i][1])), shape=(usrnum, itmnum)))
	return intMat
'''
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

def tran_to_sym(R):
	adj_mat = sp.dok_matrix((usrnum + itmnum, usrnum + itmnum), dtype=np.float32)
	adj_mat = adj_mat.tolil()
	R = R.tolil()
	adj_mat[:usrnum, usrnum:] = R
	adj_mat[usrnum:, :usrnum] = R.T
	adj_mat = adj_mat.tocsr()
	return adj_mat#+sp.eye(adj_mat.shape[0])

def tran_to_norm(adj):
	adj = adj + sp.eye(adj.shape[0])
	adjNorm=np.reshape(np.array(np.sum(adj, axis=1)), [-1])
	# tpadjNorm[kk] = np.reshape(np.array(np.sum(tpadj[kk], axis=1)), [-1])
	for i in range(adj.shape[0]):
		for j in range(adj.indptr[i], adj.indptr[i+1]):
			adj.data[j] /= adjNorm[i]
	return adj
	
def normalized_adj_single(adj):
	rowsum = np.array(adj.sum(1))

	d_inv = np.power(rowsum, -1).flatten()
	d_inv[np.isinf(d_inv)] = 0.
	d_mat_inv = sp.diags(d_inv)
	print(d_mat_inv)
	print("adj",adj)
	norm_adj = d_mat_inv.dot(adj)
	print(norm_adj)
	# norm_adj = adj.dot(d_mat_inv)
	print('generate single-normalized adjacency matrix.')
	return norm_adj.tocsr()

def trans(interaction, usrnum, itmnum):
	global minn
	global maxx
	rcd = [list(), list(), list()]
	for usr in range(usrnum):
		if interaction[usr] == None:
			continue
		data = interaction[usr]
		for col in data:
			if data[col] != None:
				for one_data in data[col]:
					rcd[0].append(usr)
					rcd[1].append(col)
					rcd[2].append(1.0)
	intMat=csr_matrix((rcd[2], (rcd[0], rcd[1])), shape=(usrnum, itmnum))
	return intMat

prefix = 'D:/edgedownload/'
print('Start')
interaction, usrnum, itmnum = mapping(prefix + 'Gowalla_totalCheckins.txt')
print('Id Mapped, usr %d, itm %d' % (usrnum, itmnum))

checkFuncs = [checkFunc1, checkFunc2, checkFunc3]
for i in range(3):
	filterItem = True if i < 1 else False
	interaction, usrnum, itmnum = filter(interaction, usrnum, itmnum, checkFuncs[i], checkFuncs[i], filterItem)
	print('Filter', i, 'times:', usrnum, itmnum)
print('Sparse Samples Filtered, usr %d, itm %d' % (usrnum, itmnum))

trnInt, tstInt = split(interaction, usrnum, itmnum)
print('Datasets Splited')
# print(trnInt)
trnMat = [trans(trnInt, usrnum, itmnum)]
subMat,timeMat=trans_sub(trnInt, usrnum, itmnum, 8)
print(timeMat)
trnMat.append(subMat)
trnMat.append(timeMat)
print('Train Mat Done')
with open(prefix+'trn_mat_time', 'wb') as fs:
	pickle.dump(trnMat, fs)
'''
with open(prefix+'tst_int', 'wb') as fs:
	pickle.dump(tstInt, fs)
'''
print('Interaction Data Saved')