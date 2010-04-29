import constants

def generate_pyx(program_unit_list, buf):
    buf.write('''
cimport DP_c

cpdef api DP_c.fwrap_default_int empty_func():
    return DP_c.empty_func_c()
'''
)

def generate_pxd(program_unit_list, buf):
    buf.write('''
cimport DP_c

cpdef api DP_c.fwrap_default_int empty_func()
'''
)

class CyArgWrapper(object):

    def __init__(self, arg):
        self.arg = arg

    def extern_declarations(self):
        return ["%s %s" % (self.arg.get_ktp(), self.arg.get_name())]

    def intern_declarations(self):
        return []

    def intern_name(self):
        return self.arg.get_name()

class CyArrayArgWrapper(object):

    def __init__(self, arg):
        self.arg = arg

    def extern_declarations(self):
        return ['object %s' % self.arg.intern_name()]

    def intern_declarations(self):
        return ["cdef np.ndarray[%s, ndim=%d, mode='fortran'] %s_ = %s" % \
                (self.arg.get_ktp(),
                 self.arg.get_ndims(),
                 self.arg.intern_name(),
                 self.arg.intern_name())
                ]
                 
    def call_arg_list(self):
        shapes = reversed(['&%s_.shape[%d]' % (self.arg.intern_name(), i) \
                                for i in range(self.arg.get_ndims())])
        data = '<%s*>%s_.data' % (self.arg.get_ktp(), self.arg.intern_name())
        return list(shapes) + [data]

FW_RETURN_VAR_NAME = 'fwrap_return_var'
class CyArgWrapperManager(object):

    def __init__(self, args, return_type_name):
        self.args = args
        self.return_type_name = return_type_name

    @classmethod
    def from_fwrapped_proc(cls, fw_proc):
        fw_arg_man = fw_proc.arg_man
        args = [CyArgWrapper(fw_arg) for fw_arg in fw_arg_man.arg_wrappers]
        return_wpr = fw_arg_man.return_arg_wrapper
        rtn = 'object'
        if return_wpr:
            rtn = return_wpr.get_ktp()
        return cls(args=args, return_type_name=rtn)

    def call_arg_list(self):
        return ["&%s" % arg.intern_name() for arg in self.args]

    def arg_declarations(self):
        decls = []
        for arg in self.args:
            decls.extend(arg.extern_declarations())
        return decls

    def return_arg_declaration(self):
        return ["cdef %s %s" % (self.return_type_name, FW_RETURN_VAR_NAME)]

def wrap_fc(ast):
    ret = []
    for proc in ast:
        ret.append(ProcWrapper(wrapped=proc))
    return ret

def generate_pxd_fc(ast, fc_header_name, buf):
    buf.putln("from %s cimport *" % constants.KTP_PXD_HEADER_NAME)
    buf.putln('')
    buf.putln('cdef extern from "%s":' % fc_header_name)
    buf.indent()
    for proc in ast:
        buf.putln(proc.cy_prototype())
    buf.dedent()

class ProcWrapper(object):
    
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = self.wrapped.wrapped_name()
        self.arg_mgr = CyArgWrapperManager.from_fwrapped_proc(wrapped)

    def cy_prototype(self):
        cp = self.wrapped.c_prototype()
        return cp.strip(";")

    def proc_declaration(self):
        template = "cpdef api %(return_type_name)s %(proc_name)s(%(arg_list)s):"
        arg_list = ', '.join(self.arg_mgr.arg_declarations())
        sdict = dict(return_type_name=self.arg_mgr.return_type_name,
                proc_name=self.name,
                arg_list=arg_list)
        return template % sdict

    def proc_call(self):
        proc_call = "%(call_name)s(%(call_arg_list)s)" % {
                'call_name' : self.wrapped.name,
                'call_arg_list' : ', '.join(self.arg_mgr.call_arg_list())}
        if self.wrapped.kind == 'subroutine':
            return proc_call
        else:
            return '%s = %s' % (FW_RETURN_VAR_NAME, proc_call)

    def temp_declarations(self):
        if self.wrapped.kind == 'function':
            return self.arg_mgr.return_arg_declaration()
        else:
            return []

    def return_statement(self):
        if self.wrapped.kind == 'function':
            return 'return %s' % FW_RETURN_VAR_NAME

    def generate_wrapper(self, buf):
        buf.putln(self.proc_declaration())
        buf.indent()
        for decl in self.temp_declarations():
            buf.putln(decl)
        buf.putln(self.proc_call())
        if self.wrapped.kind == 'function':
            buf.putln(self.return_statement())
        buf.dedent()
