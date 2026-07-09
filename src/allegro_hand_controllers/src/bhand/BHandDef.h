/*
 * Software License Agreement (BSD License)
 *
 *  Copyright (c) 2016, Wonik Robotics.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *   * Neither the name of Wonik Robotics nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 */

/**
 * @file BHandDef.h
 * @brief Definitions.
 */
#ifndef __BHANDDEF_H__
#define __BHANDDEF_H__

/* DLL export */
#if defined(WIN32) || defined(WINCE)
#    if defined(BHAND_EXPORTS)
#        define BHANDEXPORT __declspec(dllexport)
#    elif defined(BHAND_IMPORTS)
#        define BHANDEXPORT __declspec(dllimport)
#    else
#        define BHANDEXPORT
#    endif
#else
#    define BHANDEXPORT
#endif


#ifdef __cplusplus
#    define BHAND_EXTERN_C_BEGIN    extern "C" {
#    define BHAND_EXTERN_C_END    }
#else
#    define BHAND_EXTERN_C_BEGIN
#    define BHAND_EXTERN_C_END
#endif

#ifndef DEG2RAD
#define DEG2RAD (3.141592f/180.0f)
#endif

#ifndef RAD2DEG
#define RAD2DEG (180.0f/3.141592f)
#endif

#endif // __BHANDDEF_H__
