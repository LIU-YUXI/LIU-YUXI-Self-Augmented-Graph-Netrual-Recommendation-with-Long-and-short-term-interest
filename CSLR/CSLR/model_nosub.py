from ast import arg
from Params import args
import Utils.NNLayers as NNs
from Utils.NNLayers import FC, Regularize, Activate, Dropout, Bias, getParam, defineParam, defineRandomNameParam
import tensorflow as tf
from tensorflow.core.protobuf import config_pb2
import pickle
import Utils.TimeLogger as logger
import numpy as np
from Utils.TimeLogger import log
from DataHandler import negSamp, transpose, DataHandler, transToLsts
from Utils.attention import AdditiveAttention,MultiHeadSelfAttention
class Recommender0:
	def __init__(self, sess, handler):
		self.sess = sess
		self.handler = handler

		print('USER', args.user, 'ITEM', args.item)
		self.metrics = dict()
		mets = ['Loss', 'preLoss', 'HR', 'NDCG']
		for met in mets:
			self.metrics['Train' + met] = list()
			self.metrics['Test' + met] = list()

	def makePrint(self, name, ep, reses, save):
		ret = 'Epoch %d/%d, %s: ' % (ep, args.epoch, name)
		for metric in reses:
			val = reses[metric]
			ret += '%s = %.4f, ' % (metric, val)
			tem = name + metric
			if save and tem in self.metrics:
				self.metrics[tem].append(val)
		ret = ret[:-2] + '  '
		return ret

	def run(self):
		self.prepareModel()
		log('Model Prepared')
		if args.load_model != None:
			self.loadModel()
			stloc = len(self.metrics['TrainLoss']) * args.tstEpoch - (args.tstEpoch - 1)
		else:
			stloc = 0
			init = tf.global_variables_initializer()
			self.sess.run(init)
			log('Variables Inited')
		for ep in range(stloc, args.epoch):
			test = (ep % args.tstEpoch == 0)
			reses = self.trainEpoch()
			log(self.makePrint('Train', ep, reses, test))
			if test:
				reses = self.testEpoch()
				log(self.makePrint('Test', ep, reses, test))
			if ep % args.tstEpoch == 0:
				self.saveHistory()
			print()
		reses = self.testEpoch()
		log(self.makePrint('Test', args.epoch, reses, True))
		self.saveHistory()
	# def LightGcn(self, adj, )
	'''
	def messagePropagate(self, lats, adj):
		# GAT=GraphAttentionLayer(lats.shape[-1],lats.shape[-1],adj,args.user+args.item)
		# return GAT.call(lats)
		return Activate(tf.sparse.sparse_dense_matmul(adj, lats), self.actFunc)
		# return tf.sparse.sparse_dense_matmul(adj, lats)
	def hyperPropagate(self, lats, adj):
		# return adj @ (tf.transpose(adj) @ lats)
		# return FC(adj @ Activate(tf.transpose(adj) @ lats, self.actFunc), args.latdim, activation=self.actFunc)
		return Activate(adj @ Activate(tf.transpose(adj) @ lats, self.actFunc), self.actFunc)
	# act(user * item * item * dim) = user * dim
	# FC(dim*item)=dim*hyperNum
	# hyperNum*dim + user*dim
	# ????????????????????????dropout??????
	'''
	def hyperPropagate(self, lats, adj):
		lat1 = Activate(tf.transpose(adj) @ lats, self.actFunc)
		lat2 = tf.transpose(FC(tf.transpose(lat1), args.hyperNum, activation=self.actFunc)) + lat1
		lat3 = tf.transpose(FC(tf.transpose(lat2), args.hyperNum, activation=self.actFunc)) + lat2
		lat4 = tf.transpose(FC(tf.transpose(lat3), args.hyperNum, activation=self.actFunc)) + lat3
		# lat5 = tf.transpose(FC(tf.transpose(lat4), args.hyperNum, activation=self.actFunc)) + lat3
		ret = Activate(adj @ lat4, self.actFunc)
		# print("LATS",lat1,lat2,lat3,lat4,ret)
		# ret = adj @ lat4
		return ret
	def edgeDropout(self, mat):
		def dropOneMat(mat):
			print("drop",mat)
			indices = mat.indices
			values = mat.values
			shape = mat.dense_shape
			# newVals = tf.to_float(tf.sign(tf.nn.dropout(values, self.keepRate)))
			newVals = tf.nn.dropout(values, self.keepRate)
			return tf.sparse.SparseTensor(indices, newVals, shape)
		return dropOneMat(mat)
	# cross-view collabrative Supervision
	def ours(self):
		all_emb0=list()
		all_emb1=list()
		uEmbed=NNs.defineParam('uEmbed', [args.user, args.latdim], reg=True)
		iEmbed=NNs.defineParam('iEmbed', [args.item, args.latdim], reg=True)	
		uhyper = NNs.defineParam('uhyper', [args.latdim, args.hyperNum], reg=True)
		ihyper = NNs.defineParam('ihyper', [args.latdim, args.hyperNum], reg=True)
		uuHyper = (uEmbed @ uhyper)
		iiHyper = (iEmbed @ ihyper)
		all_emb0=uEmbed
		all_emb1=iEmbed
		embs0=[all_emb0]
		embs1=[all_emb1]
		for i in range(args.gnn_layer):
			all_emb= tf.concat([embs0[-1],embs1[-1]],axis=0)
			all_emb = Activate(tf.sparse.sparse_dense_matmul(self.edgeDropout(self.adj), all_emb), self.actFunc)
			all_emb0,all_emb1 = tf.split(all_emb,[args.user,args.item],axis=0)
			# all_emb0 = Activate(tf.sparse.sparse_dense_matmul(self.edgeDropout(self.adj[0:args.user,args.user:]), embs1[i]), self.actFunc)
			# all_emb1 = Activate(tf.sparse.sparse_dense_matmul(self.edgeDropout(self.adj[args.user:,0:args.user]), embs0[i]), self.actFunc)
			hyperULat = self.hyperPropagate(embs0[-1], tf.nn.dropout(uuHyper, self.keepRate))
			hyperILat = self.hyperPropagate(embs1[-1], tf.nn.dropout(iiHyper, self.keepRate))
			embs0.append(all_emb0+embs0[-1]+hyperULat)
			embs1.append(all_emb1+embs1[-1]+hyperILat)
		'''
		embs0 = tf.stack(embs0,axis=1) # k,u+i,latdim  [[1,1],[1,1],[1,1]]->[[1,1,1],[1,1,1]]
		embs0 = tf.reduce_mean(embs0,axis=1)
		embs1 = tf.stack(embs1,axis=1)
		embs1 = tf.reduce_mean(embs1,axis=1)
		'''
		user=tf.add_n(embs0)
		item=tf.add_n(embs1)
		pckUlat = tf.nn.embedding_lookup(user, self.uids)
		pckIlat = tf.nn.embedding_lookup(item, self.iids)
		preds = tf.reduce_sum(pckUlat * pckIlat, axis=-1) # [uids,dim] * [iids,dim] emmm maybe there is a dot multiply
		'''
		def calcSSL(hyperLat, gnnLat):
			posScore = tf.exp(tf.reduce_sum(hyperLat * gnnLat, axis=1) / args.temp)
			negScore = tf.reduce_sum(tf.exp(gnnLat @ tf.transpose(hyperLat) / args.temp), axis=1)
			uLoss = tf.reduce_sum(-tf.log(posScore / (negScore + 1e-8) + 1e-8))
			return uLoss
		'''
		sslloss = 0	
		return preds, 1-sslloss

	def prepareModel(self):
		self.keepRate = tf.placeholder(dtype=tf.float32, shape=[])
		NNs.leaky = args.leaky
		self.actFunc = 'leakyRelu'
		adj = self.handler.trnMat
		idx, data, shape = transToLsts(adj, norm=True)
		self.adj = tf.sparse.SparseTensor(idx, data, shape)
		idx, data, shape = transToLsts(transpose(adj), norm=True)
		print("idx,data,shape",idx,data,shape)
		self.tpAdj = tf.sparse.SparseTensor(idx, data, shape)
		self.uids = tf.placeholder(name='uids', dtype=tf.int32, shape=[None])
		self.iids = tf.placeholder(name='iids', dtype=tf.int32, shape=[None])
		self.suids=list()
		self.siids=list()
		for k in range(args.graphNum):
			self.suids.append(tf.placeholder(name='suids%d'%k, dtype=tf.int32, shape=[None]))
			self.siids.append(tf.placeholder(name='siids%d'%k, dtype=tf.int32, shape=[None]))
		self.subAdj=list()
		for i in range(args.graphNum):
			seqadj = self.handler.subadj[i]
			idx, data, shape = transToLsts(seqadj, norm=True)
			self.subAdj.append(tf.sparse.SparseTensor(idx, data, shape))

		self.preds, self.sslloss = self.ours()
		sampNum = tf.shape(self.uids)[0] // 2
		posPred = tf.slice(self.preds, [0], [sampNum])# begin at 0, size = sampleNum
		negPred = tf.slice(self.preds, [sampNum], [-1])# 
		self.preLoss = tf.reduce_sum(tf.maximum(0.0, 1.0 - (posPred - negPred))) / args.batch
		self.regLoss = args.reg * Regularize() + args.ssl_reg * self.sslloss
		self.loss = self.preLoss + self.regLoss

		globalStep = tf.Variable(0, trainable=False)
		learningRate = tf.train.exponential_decay(args.lr, globalStep, args.decay_step, args.decay, staircase=True)
		self.optimizer = tf.train.AdamOptimizer(learningRate).minimize(self.loss, global_step=globalStep)

	def sampleTrainBatch(self, batIds, labelMat):
		temLabel=labelMat[batIds].toarray()
		batch = len(batIds)
		temlen = batch * 2 * args.sampNum
		uLocs = [None] * temlen
		iLocs = [None] * temlen
		cur = 0				
		for i in range(batch):
			posset = np.reshape(np.argwhere(temLabel[i]!=0), [-1])
			sampNum = min(args.sampNum, len(posset))
			if sampNum == 0:
				poslocs = [np.random.choice(args.item)]
				neglocs = [poslocs[0]]
			else:
				poslocs = np.random.choice(posset, sampNum)
				neglocs = negSamp(temLabel[i], sampNum, args.item)
			for j in range(sampNum):
				posloc = poslocs[j]
				negloc = neglocs[j]
				uLocs[cur] = uLocs[cur+temlen//2] = batIds[i]
				iLocs[cur] = posloc
				iLocs[cur+temlen//2] = negloc
				cur += 1
		# ???????????????????????????user????????????
		uLocs = uLocs[:cur] + uLocs[temlen//2: temlen//2 + cur]
		iLocs = iLocs[:cur] + iLocs[temlen//2: temlen//2 + cur]
		# print(uLocs[0],uLocs[1],iLocs[0],iLocs[1])
		return uLocs, iLocs

	def sampleSslBatch(self, batIds, labelMat):
		temLabel=list()
		for k in range(args.graphNum):	
			temLabel.append(labelMat[k][batIds].toarray())
		batch = len(batIds)
		temlen = batch * 2 * args.sslNum
		uLocs = [[None] * temlen] * args.graphNum
		iLocs = [[None] * temlen] * args.graphNum
		for k in range(args.graphNum):	
			cur = 0				
			for i in range(batch):
				posset = np.reshape(np.argwhere(temLabel[k][i]!=0), [-1])
				sslNum = min(args.sslNum, len(posset)//2)
				if sslNum == 0:
					poslocs = [np.random.choice(args.item)]
					neglocs = [poslocs[0]]
				else:
					all = np.random.choice(posset, sslNum*2)
					poslocs = all[:sslNum]
					neglocs = all[sslNum:]
				for j in range(sslNum):
					posloc = poslocs[j]
					negloc = neglocs[j]
					uLocs[k][cur] = uLocs[k][cur+temlen//2] = batIds[i]
					iLocs[k][cur] = posloc
					iLocs[k][cur+temlen//2] = negloc
					cur += 1
			# ???????????????????????????user????????????
			uLocs[k] = uLocs[k][:cur] + uLocs[k][temlen//2: temlen//2 + cur]
			iLocs[k] = iLocs[k][:cur] + iLocs[k][temlen//2: temlen//2 + cur]
		# print(uLocs[0],uLocs[1],iLocs[0],iLocs[1])
		return uLocs, iLocs

	def trainEpoch(self):
		num = args.user
		sfIds = np.random.permutation(num)[:args.trnNum]
		epochLoss, epochPreLoss = [0] * 2
		num = len(sfIds)
		steps = int(np.ceil(num / args.batch))

		for i in range(steps):
			st = i * args.batch
			ed = min((i+1) * args.batch, num)
			batIds = sfIds[st: ed]

			target = [self.optimizer, self.preLoss, self.regLoss, self.loss, self.preds]
			feed_dict = {}
			uLocs, iLocs = self.sampleTrainBatch(batIds, self.handler.trnMat)
			suLocs, siLocs = self.sampleSslBatch(batIds, self.handler.subadj)
			feed_dict[self.uids] = uLocs
			feed_dict[self.iids] = iLocs
			for k in range(args.graphNum):
				feed_dict[self.suids[k]] = suLocs[k]
				feed_dict[self.siids[k]] = siLocs[k]
			# print(len(suLocs),len(siLocs))
			feed_dict[self.keepRate] = args.keepRate

			res = self.sess.run(target, feed_dict=feed_dict, options=config_pb2.RunOptions(report_tensor_allocations_upon_oom=True))

			preLoss, regLoss, loss, pre = res[1:]
			if(i==20):
				print(pre)

			epochLoss += loss
			epochPreLoss += preLoss
			log('Step %d/%d: loss = %.2f, regLoss = %.2f         ' % (i, steps, loss, regLoss), save=False, oneline=True)
		ret = dict()
		ret['Loss'] = epochLoss / steps
		ret['preLoss'] = epochPreLoss / steps
		return ret

	def sampleTestBatch(self, batIds, labelMat): # labelMat=TrainMat(adj)
		batch = len(batIds)
		temTst = self.handler.tstInt[batIds]
		temLabel = labelMat[batIds].toarray()
		# print("temLabel",temLabel)
		temlen = batch * 100
		uLocs = [None] * temlen
		iLocs = [None] * temlen
		tstLocs = [None] * batch
		cur = 0
		for i in range(batch):
			posloc = temTst[i]
			rdnNegSet = negSamp(temLabel[i], 99, args.item)
			locset = np.concatenate((rdnNegSet, np.array([posloc])))
			tstLocs[i] = locset
			for j in range(100):
				uLocs[cur] = batIds[i]
				iLocs[cur] = locset[j]
				cur += 1
		return uLocs, iLocs, temTst, tstLocs

	def testEpoch(self):
		epochHit, epochNdcg = [0] * 2
		ids = self.handler.tstUsrs
		num = len(ids)
		tstBat = args.batch
		steps = int(np.ceil(num / tstBat))
		for i in range(steps):
			st = i * tstBat
			ed = min((i+1) * tstBat, num)
			batIds = ids[st: ed]
			feed_dict = {}
			uLocs, iLocs, temTst, tstLocs = self.sampleTestBatch(batIds, self.handler.trnMat)
			suLocs, siLocs = self.sampleSslBatch(batIds, self.handler.subadj)
			feed_dict[self.uids] = uLocs
			feed_dict[self.iids] = iLocs
			for k in range(args.graphNum):
				feed_dict[self.suids[k]] = suLocs[k]
				feed_dict[self.siids[k]] = siLocs[k]
			feed_dict[self.keepRate] = 1.0
			preds = self.sess.run(self.preds, feed_dict=feed_dict, options=config_pb2.RunOptions(report_tensor_allocations_upon_oom=True))
			if(i==20):
				print(preds)
			hit, ndcg = self.calcRes(np.reshape(preds, [ed-st, 100]), temTst, tstLocs)
			epochHit += hit
			epochNdcg += ndcg
			log('Steps %d/%d: hit = %d, ndcg = %d          ' % (i, steps, hit, ndcg), save=False, oneline=True)
		ret = dict()
		ret['HR'] = epochHit / num
		ret['NDCG'] = epochNdcg / num
		return ret

	def calcRes(self, preds, temTst, tstLocs):
		hit = 0
		ndcg = 0
		for j in range(preds.shape[0]):
			predvals = list(zip(preds[j], tstLocs[j]))
			predvals.sort(key=lambda x: x[0], reverse=True)
			shoot = list(map(lambda x: x[1], predvals[:args.shoot]))
			if temTst[j] in shoot:
				hit += 1
				ndcg += np.reciprocal(np.log2(shoot.index(temTst[j])+2))
		return hit, ndcg
	
	def saveHistory(self):
		if args.epoch == 0:
			return
		with open('History/' + args.save_path + '.his', 'wb') as fs:
			pickle.dump(self.metrics, fs)

		saver = tf.train.Saver()
		saver.save(self.sess, 'Models/' + args.save_path)
		log('Model Saved: %s' % args.save_path)

	def loadModel(self):
		saver = tf.train.Saver()
		saver.restore(self.sess, 'Models/' + args.load_model)
		with open('History/' + args.load_model + '.his', 'rb') as fs:
			self.metrics = pickle.load(fs)
		log('Model Loaded')	

class GraphAttentionLayer():
    def __init__(self,
                 input_dim,
                 output_dim,
                 adj,
                 nodes_num,
                 dropout_rate=0.5,
                 activation=None,
                 use_bias=True,
                 kernel_initializer='glorot_uniform',
                 bias_initializer='zeros',
                 kernel_regularizer=None,
                 bias_regularizer=None,
                 activity_regularizer=None,
                 kernel_constraint=None,
                 bias_constraint=None,
                 coef_dropout=0.5,
                 **kwargs):
        super(GraphAttentionLayer, self).__init__()
        self.use_bias = use_bias
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.support = adj# [tf.SparseTensor(indices=adj.indices, values=adj.values, dense_shape=adj.dense_shape)]
        self.dropout_rate = dropout_rate
        self.coef_drop = coef_dropout
        self.nodes_num = nodes_num
        self.kernel = None
        self.mapping = None
        self.bias = None
        # self.build()
    def call(self, inputs, training=True):
        # ????????????????????????????????????
        # inputs = tf.nn.l2_normalize(inputs, 1)
        raw_shape = inputs.shape
        inputs = tf.reshape(inputs, shape=(1, raw_shape[0], raw_shape[1]))  # (1, nodes_num, input_dim)
        # mapped_inputs = keras.layers.Conv1D(self.output_dim, 1, use_bias=False)(inputs)  # (1, nodes_num, output_dim)
        mapped_inputs = tf.layers.conv1d(inputs,self.output_dim, 1)
		# mapped_inputs = tf.nn.l2_normalize(mapped_inputs)
 
        sa_1 = tf.layers.conv1d(mapped_inputs, 1, 1)# keras.layers.Conv1D(1, 1)(mapped_inputs)  # (1, nodes_num, 1)
        sa_2 = tf.layers.conv1d(mapped_inputs, 1, 1)# keras.layers.Conv1D(1, 1)(mapped_inputs)  # (1, nodes_num, 1)
 
        con_sa_1 = tf.reshape(sa_1, shape=(raw_shape[0], 1))  # (nodes_num, 1)
        con_sa_2 = tf.reshape(sa_2, shape=(raw_shape[0], 1))  # (nodes_num, 1)
 
        # con_sa_1 = tf.cast(self.support[0], dtype=tf.float32) * con_sa_1  # (nodes_num, nodes_num) W_hi
        # con_sa_2 = tf.cast(self.support[0], dtype=tf.float32) * tf.transpose(con_sa_2, [1, 0])  # (nodes_num, nodes_num) W_hj
        con_sa_1 = self.support * con_sa_1
        con_sa_2 = self.support * tf.transpose(con_sa_2, [1, 0])
        weights = tf.sparse.add(con_sa_1, con_sa_2)  # concatenation
        weights_act = tf.SparseTensor(indices=weights.indices,
                                      values=tf.nn.leaky_relu(weights.values),
                                      dense_shape=weights.dense_shape)  # ????????????????????????
        attention = tf.sparse.softmax(weights_act)  
        inputs = tf.reshape(inputs, shape=raw_shape)
        if self.coef_drop > 0.0:
            attention = tf.SparseTensor(indices=attention.indices,
                                        values=tf.nn.dropout(attention.values, self.coef_dropout),
                                        dense_shape=attention.dense_shape)
        if training and self.dropout_rate > 0.0:
            inputs = tf.nn.dropout(inputs, self.dropout_rate)
        if not training:
            print("[GAT LAYER]: GAT not training now.")
 
        attention = tf.sparse.reshape(attention, shape=[self.nodes_num, self.nodes_num])
        # value = tf.matmul(inputs, self.kernel)
        value = tf.layers.dense(inputs,self.output_dim,use_bias=self.use_bias)
        value = tf.sparse.sparse_dense_matmul(attention, value)
        '''
        if self.use_bias:
            ret = tf.add(value, self.bias)
        else:
            ret = tf.reshape(value, (raw_shape[0], self.output_dim))
		'''
        return tf.nn.relu(value)