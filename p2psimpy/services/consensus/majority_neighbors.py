from p2psimpy.services import BaseRunner, BaseHandler
from p2psimpy import BaseMessage, GossipMessage, MsgResponse
from p2psimpy.storage import RangedStorage, Storage

class Transaction(BaseMessage):
    def get_hash(self):
        return self.data['hash']

    def __hash__(self):
        return self.data['hash']


class Consensus(BaseHandler):
    """
    Consensus based on blocks and longest-chain rule.
    Args:
        mining_time: DistAttr, Dist or value to indicate time for a mining process. 
        conf_num: number of confirmation when transaction is considered final.
        max_txs_per_block: maximum number of transaction per block.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.init_ttl = kwargs.pop('init_ttl', 3)
        self.init_fanout = kwargs.pop('init_fanout', 6)
        self.pre_task = kwargs.pop('pre_task', None)
        self.post_task = kwargs.pop('post_task', None)
        self.exclude_types = kwargs.pop('exclude_types', {'bootstrap', 'client'})
        self.exclude_peers = set()

        # initialize storage for the map: tx_id: number of confirmations 
        self.peer.add_storage('txs_conf', RangedStorage())
        self.main_strg = self.peer.storage.get('txs_conf')
        self.tx_hash_to_count = dict()
        self.tx_id_to_hash = dict()
        self.tx_hash_to_tx = dict()
        self.peer.add_storage('msg_data', Storage())
        
    def _handle_gossip_msg(self, msg):
        if isinstance(msg.data, Transaction):
            if msg.ttl > 0:
                exclude_peers = {msg.sender} | self.exclude_peers
                self.peer.gossip(GossipMessage(self.peer, msg.id, msg.data, msg.ttl - 1,
                                               pre_task=msg.pre_task, post_task=msg.post_task),
                                 self.init_fanout,
                                 except_peers=exclude_peers,
                                 except_type=self.exclude_types)

            _msg_hash = msg.data.get_hash()
            self.tx_hash_to_tx[_msg_hash] = msg
            if _msg_hash not in self.tx_hash_to_count:
                self.tx_hash_to_count[_msg_hash] = 1
                self.tx_id_to_hash[msg.id] = set()
                self.tx_id_to_hash[msg.id].add(_msg_hash)
            else:
                _pre_count = self.tx_hash_to_count[_msg_hash]
                self.tx_hash_to_count[_msg_hash] = _pre_count + 1
                self.tx_id_to_hash[msg.id].add(_msg_hash)
                if len(self.tx_id_to_hash[msg.id]) >= 3:
                    print(self.tx_id_to_hash[msg.id])
                assert len(self.tx_id_to_hash[msg.id]) <= 2

            _max_count = 0
            _max_count_hash = None
            for tx_hash in self.tx_id_to_hash[msg.id]:
                _count = self.tx_hash_to_count[tx_hash]
                if _count > _max_count:
                    _max_count_hash = tx_hash
                    _max_count = _count
            assert _max_count_hash is not None
            # Use message id as key here to store in peer storage
            _max_count_tx = self.tx_hash_to_tx[_max_count_hash]
            self.peer.store('msg_data', _max_count_tx.id, _max_count_tx)
            # print(self.peer, _max_count_tx.id ,self.tx_hash_to_tx[_max_count_hash])
            assert self.tx_hash_to_tx[_max_count_hash] is not None


    def handle_message(self, msg):
        if isinstance(msg, MsgResponse):
            for msg_id, sub_msg in msg.data.items():
                self._handle_gossip_msg(sub_msg)
        else:
            self._handle_gossip_msg(msg)
            
    @property
    def messages(self):
        return GossipMessage, MsgResponse,

