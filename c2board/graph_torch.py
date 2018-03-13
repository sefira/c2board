import torch
from distutils.version import LooseVersion

from c2board.src.graph_pb2 import GraphDef
from c2board.src.node_def_pb2 import NodeDef
from c2board.src.versions_pb2 import VersionDef
from c2board.src.attr_value_pb2 import AttrValue
from c2board.src.tensor_shape_pb2 import TensorShapeProto


def replace(name, scope):
    return '/'.join([scope[name], name])


def parse(graph):
    scope = {}
    for n in graph.nodes():
        inputs = [i.uniqueName() for i in n.inputs()]
        for i in range(1, len(inputs)):
            scope[inputs[i]] = n.scopeName()

        uname = next(iter(n.outputs())).uniqueName()
        assert n.scopeName() != '', '{} has empty scope name'.format(n)
        scope[uname] = n.scopeName()
        scope['1'] = 'input'

    nodes = []
    for n in graph.nodes():
        attrs = {k: n[k] for k in n.attributeNames()}
        attrs = str(attrs).replace("'", ' ')  # singlequote will be escaped by tensorboard
        if any(i.uniqueName() not in scope.keys() for i in n.inputs()):  # 0.3.1 workaround
            continue
        inputs = [replace(i.uniqueName(), scope) for i in n.inputs()]
        uname = next(iter(n.outputs())).uniqueName()  # FIXME: only first output is considered
        nodes.append({'name': replace(uname, scope), 
                    'op': n.kind(), 
                    'inputs': inputs, 
                    'attr': attrs})

    for n in graph.inputs():
        uname = n.uniqueName()
        if uname not in scope.keys():
            scope[uname] = 'unused'
        nodes.append({'name': replace(uname, scope), 
                    'op': 'Parameter', 
                    'inputs': [], 
                    'attr': str(n.type())})

    return nodes


def graph_torch(model, args, verbose=False):
    with torch.onnx.set_training(model, False):
        trace, _ = torch.jit.trace(model, args)
    torch.onnx._optimize_trace(trace)
    current_graph = trace.graph()
    import pdb
    pdb.set_trace()
    list_of_nodes = parse(current_graph)
    nodes = []
    for node in list_of_nodes:
        nodes.append(
            NodeDef(name=node['name'], 
                    op=node['op'], 
                    input=node['inputs'],
                    attr={'lanpa': AttrValue(s=node['attr'].encode(encoding='utf_8'))}))

    return GraphDef(node=nodes, versions=VersionDef(producer=22))